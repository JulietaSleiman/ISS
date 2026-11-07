from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from src.core.auth_manager import AuthManager
from src.core.caja_manager import CajaManager
from src.core.categorias_manager import CategoriasManager
from src.core.entity_sync_store import EntitySyncStore
from src.core.productos_manager import ProductosManager
from src.core.proveedores_manager import ProveedoresManager
from src.core.ventas_manager import VentasManager
from src.db import database


class EntitySyncCase(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(temp.cleanup)
        self.db_path = Path(temp.name) / 'test.sqlite'
        self.user = SimpleNamespace(user_id='11111111-1111-4111-8111-111111111111', username='caja1',
            branch_id='f2985c88-2a4e-4e73-92d5-85d905b3db41', role='cajero')
        self.db_patch = patch.object(database, 'DB_PATH', self.db_path)
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        for target, kw in ((database, {'auto_backup_db': lambda: None}),):
            p = patch.multiple(target, **kw)
            p.start()
            self.addCleanup(p.stop)
        for method in ('require_user', 'current_user'):
            p = patch.object(AuthManager, method, side_effect=lambda: self.user)
            p.start()
            self.addCleanup(p.stop)
        database.init_db()
        self.caja = CajaManager.abrir_caja(100)

    def sql(self, query, params=()):
        with closing(database.get_connection()) as conn:
            with conn:
                return [dict(row) for row in conn.execute(query, params).fetchall()]

    def test_received_promotion_waits_for_product_and_uses_its_local_id(self):
        from src.core.promotion_sync import apply_promotion
        from src.core.promociones_manager import PromocionesManager

        product_identity = '11111111-2222-4333-8444-555555555555'
        row = {'id': '11111111-2222-4333-8444-666666666666', 'revision': 1, 'payload': {
            'nombre': 'Combo', 'precio_fijo': 50, 'activa': True,
            'detalles': [{'producto': product_identity, 'cantidad_requerida': 2}],
        }}
        self.assertFalse(apply_promotion(self.user, row))
        self.product(codigo_barras='111')
        self.product(codigo_barras='222')
        product_id = self.sql("SELECT id FROM productos WHERE codigo_barras='222'")[0]['id']
        self.sql('UPDATE productos SET sync_id=? WHERE id=?', (product_identity, product_id))
        self.assertTrue(apply_promotion(self.user, row))
        self.assertFalse(apply_promotion(self.user, row))
        self.assertEqual(PromocionesManager.get_all()[0]['detalles'], [
            {'producto_id': product_id, 'cantidad_requerida': 2},
        ])

    def product(self, **changes):
        values = dict(codigo_barras='123', nombre='Producto', costo_lista=10, flete=0,
            utilidad_porcentaje=100, precio_contado=20, precio_tarjeta=25,
            stock_actual=20, stock_minimo=5)
        values.update(changes)
        return ProductosManager.crear_producto(**values)

    def edit(self, product_id, **changes):
        fields = ('codigo_barras', 'nombre', 'costo_lista', 'flete', 'utilidad_porcentaje',
            'precio_contado', 'precio_tarjeta', 'stock_actual', 'stock_minimo', 'stock_maximo',
            'categoria_id', 'proveedor_id', 'codigo_fabrica', 'unidades_bulto', 'ubicacion', 'observaciones')
        previous = ProductosManager.get_by_id(product_id)
        values = {field: previous[field] for field in fields}
        values.update(changes)
        return ProductosManager.actualizar_producto(product_id, **values)

    def events(self, kind=None):
        rows = self.sql('SELECT * FROM sync_entidades ORDER BY rowid' + (' ' if kind else ''))
        return [dict(row, payload=json.loads(row['payload'])) for row in rows if kind is None or row['tipo'] == kind]


class EntitySyncTests(EntitySyncCase):
    def test_every_product_mutation_captures_final_state_and_separates_catalog_from_stock(self):
        product_id = self.product()
        ProductosManager.actualizar_stock(product_id, -3)
        self.edit(product_id, stock_actual=14)
        self.edit(product_id, nombre='Nombre nuevo')
        ProductosManager.eliminar_producto(product_id)
        ProductosManager.restaurar_producto(product_id)
        events = self.events('PRODUCTO')
        self.assertEqual([e['revision'] for e in events], [1, 2, 3, 4, 5, 6])
        self.assertEqual([e['payload']['catalog_revision'] for e in events], [1, 1, 1, 2, 3, 4])
        self.assertEqual([e['payload']['stock_actual'] for e in events], [20, 17, 14, 14, 14, 14])
        self.assertFalse(events[-2]['payload']['activo'])
        self.assertTrue(events[-1]['payload']['activo'])
        self.assertEqual(len({e['entidad_id'] for e in events}), 1)
        self.assertEqual(len({e['id'] for e in events}), 6)
        self.assertTrue(all(e['sucursal_id'] == self.user.branch_id for e in events))

    def test_failed_product_capture_rolls_back_business_change_and_revision(self):
        product_id = self.product()
        self.sql("CREATE TRIGGER fail_entity BEFORE INSERT ON sync_entidades BEGIN SELECT RAISE(ABORT, 'outbox full'); END")
        before = self.sql('SELECT * FROM productos')[0]
        with self.assertRaises(sqlite3.IntegrityError):
            ProductosManager.actualizar_stock(product_id, -5)
        self.assertEqual(self.sql('SELECT * FROM productos')[0], before)
        with self.assertRaises(sqlite3.IntegrityError):
            self.product(codigo_barras='different')
        self.assertEqual(len(self.sql('SELECT * FROM productos')), 1)

    def test_invalid_product_prices_do_not_create_events_or_rewrite_legacy_data(self):
        for changes in ({'precio_contado': -1}, {'precio_tarjeta': float('inf')}, {'precio_contado': 100_000_000_000_000}):
            with self.assertRaises(ValueError):
                self.product(**changes)
        self.assertEqual(self.sql('SELECT * FROM productos'), [])
        self.sql("INSERT INTO productos(nombre,precio_contado) VALUES ('Legado inválido',-1)")
        with self.assertRaisesRegex(ValueError, 'producto #1.*precios negativos'):
            EntitySyncStore.prepare_initial_sync(self.user)
        legacy = self.sql('SELECT precio_contado,sync_id,sync_revision FROM productos')[0]
        self.assertEqual(legacy, {'precio_contado': -1, 'sync_id': None, 'sync_revision': 0})
        self.assertEqual(self.events(), [])

    def test_installation_binding_can_be_validated_even_with_invalid_legacy_products(self):
        self.sql("INSERT INTO productos(nombre,precio_contado) VALUES ('Legado inválido',-1)")
        EntitySyncStore.validate_installation(self.user)
        self.assertEqual(self.sql('SELECT value FROM sync_configuracion')[0]['value'], self.user.branch_id)
        with self.assertRaises(ValueError):
            EntitySyncStore.prepare_initial_sync(self.user)
        # El dato inválido no impide cerrar la caja y preservar su resumen válido.
        CajaManager.cerrar_caja(100)
        self.assertEqual(len(self.sql('SELECT * FROM sync_cierres')), 1)

    def test_sale_captures_one_final_stock_per_product_and_original_promo_components(self):
        first = self.product(stock_actual=3)
        second = self.product(codigo_barras='456', nombre='Segundo', stock_actual=20)
        promo = self.sql("INSERT INTO promociones(nombre,precio_fijo) VALUES ('Combo',50) RETURNING id")[0]['id']
        self.sql('INSERT INTO promocion_detalles(promocion_id,producto_id,cantidad_requerida) VALUES (?,?,2)', (promo, first))
        carrito = [
            {'producto_id': first, 'cantidad': 2, 'precio_unitario': 20},
            {'es_promo': True, 'promocion_id': promo, 'cantidad': 2, 'precio_unitario': 50,
             'detalles': [{'producto_id': first, 'cantidad_requerida': 2}, {'producto_id': second, 'cantidad_requerida': 1}]},
            {'producto_id': first, 'cantidad': 1, 'precio_unitario': 20},
        ]
        result = VentasManager.procesar_venta(1, 'EFECTIVO', carrito)
        products = self.events('PRODUCTO')
        self.assertEqual(len(products), 4)  # dos altas y dos estados finales, sin duplicar renglones.
        finals = {p['payload']['local_id']: p['payload'] for p in products[-2:]}
        self.assertEqual(finals[first]['stock_actual'], -4)  # stock negativo sigue permitido.
        self.assertEqual(finals[second]['stock_actual'], 18)
        self.assertEqual(finals[first]['catalog_revision'], 1)
        sale = self.events('VENTA')[0]['payload']
        self.assertFalse(sale['historica'])
        self.assertEqual(sale['vendedor_id'], self.user.user_id)
        self.assertEqual(sale['local_id'], result['venta_id'])
        self.assertTrue(sale['fecha'].endswith('Z'))
        self.assertEqual(sale['total'], 160)
        self.assertEqual(sale['detalles'][1]['componentes'], [
            {'producto_id': finals[first]['id'], 'nombre': 'Producto', 'cantidad_requerida': 2},
            {'producto_id': finals[second]['id'], 'nombre': 'Segundo', 'cantidad_requerida': 1},
        ])
        # Renombrar el catálogo/composición no reescribe el snapshot de esa venta.
        self.sql("UPDATE productos SET nombre='Renombrado' WHERE id=?", (first,))
        self.sql('DELETE FROM promocion_detalles WHERE promocion_id=?', (promo,))
        with closing(database.get_connection()) as conn:
            with conn:
                EntitySyncStore.queue_sale(conn, result['venta_id'], self.user)
        again = self.events('VENTA')[-1]['payload']
        self.assertEqual(again['detalles'], sale['detalles'])

    def test_sale_outbox_failure_rolls_back_sale_stock_details_and_cash(self):
        product_id = self.product()
        before = self.sql('SELECT * FROM productos')[0]
        self.sql("CREATE TRIGGER fail_sale_event BEFORE INSERT ON sync_entidades WHEN NEW.tipo='VENTA' BEGIN SELECT RAISE(ABORT, 'outbox full'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            VentasManager.procesar_venta(1, 'EFECTIVO', [{'producto_id': product_id, 'cantidad': 2, 'precio_unitario': 20}])
        self.assertEqual(self.sql('SELECT * FROM productos')[0], before)
        for table in ('ventas', 'ventas_detalle', 'caja_movimientos'):
            self.assertEqual(self.sql(f'SELECT * FROM {table}'), [])
        self.assertEqual(len(self.events()), 1)

    def test_sale_capture_preserves_original_seller_when_admin_resends(self):
        product_id = self.product()
        sale = VentasManager.procesar_venta(1, 'EFECTIVO', [{'producto_id': product_id, 'cantidad': 1, 'precio_unitario': 20}])
        original_seller = self.user.user_id
        self.user.user_id = '22222222-2222-4222-8222-222222222222'
        with closing(database.get_connection()) as conn:
            with self.assertRaises(ValueError):
                with conn:
                    EntitySyncStore.queue_sale(conn, sale['venta_id'], self.user)
        self.user.role = 'admin'
        with closing(database.get_connection()) as conn:
            with conn:
                EntitySyncStore.queue_sale(conn, sale['venta_id'], self.user)
        event = self.events('VENTA')[-1]
        self.assertEqual(event['usuario_id'], original_seller)
        self.assertEqual(event['payload']['vendedor_id'], original_seller)
        self.assertFalse(event['payload']['historica'])

    def test_backfill_is_idempotent_preserves_historical_costs_and_unknown_seller(self):
        self.sql("INSERT INTO productos(nombre,codigo_barras,costo_final,stock_actual) VALUES ('Histórico','old',999,5)")
        self.sql("INSERT INTO promociones(nombre,precio_fijo) VALUES ('Promo actual',30)")
        sale = self.sql("INSERT INTO ventas(cliente_id,caja_sesion_id,subtotal,total,metodo_pago,fecha) VALUES (1,?,30,30,'EFECTIVO','2025-01-01 12:00:00') RETURNING id", (self.caja,))[0]['id']
        self.sql('INSERT INTO ventas_detalle(venta_id,promocion_id,cantidad,precio_unitario,costo_unitario,subtotal) VALUES (?,1,1,30,0,30)', (sale,))
        self.sql('INSERT INTO promocion_detalles(promocion_id,producto_id,cantidad_requerida) VALUES (1,1,99)')
        database.init_db()
        EntitySyncStore.prepare_initial_sync(self.user)
        first = self.events()
        EntitySyncStore.prepare_initial_sync(self.user)
        database.init_db()
        self.assertEqual(self.events(), first)
        self.assertEqual(EntitySyncStore.initial_pending_count(self.user), 0)
        historical = self.events('VENTA')[0]['payload']
        self.assertIsNone(historical['vendedor_id'])
        self.assertTrue(historical['historica'])
        self.assertEqual(historical['detalles'][0]['costo_unitario'], 0)
        self.assertEqual(historical['detalles'][0]['componentes'], [])
        self.assertIn('nombre actual; venta histórica', historical['detalles'][0]['nombre'])
        self.assertEqual(self.sql('SELECT costo_unitario FROM ventas_detalle')[0]['costo_unitario'], 0)

    def test_bootstrap_batches_have_durable_cursor_and_pending_includes_unqueued_rows(self):
        with closing(database.get_connection()) as conn:
            with conn:
                conn.executemany('INSERT INTO productos(nombre) VALUES (?)', [(f'P{i}',) for i in range(205)])
        EntitySyncStore.prepare_initial_sync(self.user)
        self.assertEqual(len(self.events()), 200)
        self.assertEqual(EntitySyncStore.initial_pending_count(self.user), 5)
        EntitySyncStore.prepare_initial_sync(self.user)
        self.assertEqual(len(self.events()), 205)
        self.assertEqual(EntitySyncStore.initial_pending_count(self.user), 0)

    def test_binding_rejects_other_branch_and_same_local_ids_have_different_global_ids(self):
        product_id = self.product()
        first = self.events()[0]['payload']
        original_branch = self.user.branch_id
        self.user.branch_id = '22222222-2222-4222-8222-222222222222'
        with self.assertRaisesRegex(ValueError, 'otra sucursal'):
            ProductosManager.actualizar_stock(product_id, 1)
        with self.assertRaisesRegex(ValueError, 'otra sucursal'):
            EntitySyncStore.prepare_initial_sync(self.user)
        self.assertEqual(ProductosManager.get_by_id(product_id)['stock_actual'], 20)
        with patch.object(database, 'DB_PATH', self.db_path.parent / 'second.sqlite'):
            database.init_db()
            other_local_id = self.product()
            second = self.events()[0]['payload']
        self.assertEqual(product_id, other_local_id)
        self.assertNotEqual(first['id'], second['id'])
        self.assertEqual(first['codigo_barras'], second['codigo_barras'])
        self.assertEqual(first['sucursal_id'], original_branch)
        self.assertEqual(second['sucursal_id'], self.user.branch_id)

    def test_bound_database_blocks_opening_a_cash_turn_for_another_branch(self):
        self.product()
        CajaManager.cerrar_caja(100)
        self.user.branch_id = '22222222-2222-4222-8222-222222222222'
        with self.assertRaisesRegex(ValueError, 'vinculada a otra sucursal'):
            CajaManager.abrir_caja(100)
        with self.assertRaisesRegex(ValueError, 'vinculada a otra sucursal'):
            CajaManager.obtener_sesion_activa()
        self.assertEqual(len(self.sql('SELECT * FROM caja_sesiones')), 1)

    def test_related_name_changes_capture_product_labels_and_rollback_with_outbox(self):
        category = self.sql("INSERT INTO categorias(nombre) VALUES ('Bebidas') RETURNING id")[0]['id']
        supplier = self.sql("INSERT INTO proveedores(nombre) VALUES ('Proveedor') RETURNING id")[0]['id']
        product_id = self.product(categoria_id=category, proveedor_id=supplier)
        CategoriasManager.actualizar_categoria(category, 'Bebidas frías')
        ProveedoresManager.actualizar_proveedor(supplier, 'Distribuidor', 'privado', 'privada')
        snapshots = self.events('PRODUCTO')
        self.assertEqual(len(snapshots), 3)
        self.assertEqual(snapshots[1]['payload']['categoria_nombre'], 'Bebidas frías')
        self.assertEqual(snapshots[2]['payload']['proveedor_nombre'], 'Distribuidor')
        self.assertEqual([e['payload']['catalog_revision'] for e in snapshots], [1, 1, 1])
        self.assertNotIn('telefono', snapshots[-1]['payload'])
        self.sql("CREATE TRIGGER fail_rename BEFORE INSERT ON sync_entidades BEGIN SELECT RAISE(ABORT, 'outbox full'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            CategoriasManager.actualizar_categoria(category, 'No confirmado')
        self.assertEqual(self.sql('SELECT nombre FROM categorias')[0]['nombre'], 'Bebidas frías')
        self.assertEqual(ProductosManager.get_by_id(product_id)['sync_revision'], 3)
        with self.assertRaises(Exception):
            CategoriasManager.eliminar_categoria(category)
        self.assertEqual(len(self.sql('SELECT * FROM categorias')), 1)

    def test_new_sales_reject_invalid_cart_or_cost_without_events_or_stock_changes(self):
        product_id = self.product()
        for cart in ([], [{'producto_id': product_id, 'cantidad': 0, 'precio_unitario': 20}],
                     [{'producto_id': product_id, 'cantidad': float('inf'), 'precio_unitario': 20}],
                     [{'producto_id': product_id, 'cantidad': 1, 'precio_unitario': -1}]):
            with self.assertRaises(ValueError):
                VentasManager.procesar_venta(1, 'EFECTIVO', cart)
        self.sql('UPDATE productos SET costo_final=-1 WHERE id=?', (product_id,))
        with self.assertRaises(ValueError):
            VentasManager.procesar_venta(1, 'EFECTIVO', [{'producto_id': product_id, 'cantidad': 1, 'precio_unitario': 20}])
        self.assertEqual(self.sql('SELECT * FROM ventas'), [])
        self.assertEqual(len(self.events()), 1)


if __name__ == '__main__':
    unittest.main()
