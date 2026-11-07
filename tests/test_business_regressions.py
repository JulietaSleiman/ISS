import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.db import database
from src.core.caja_manager import CajaManager
from src.core.cta_cte_proveedores_manager import CtaCteProveedoresManager
from src.core.reportes_manager import ReportesManager


class BusinessRegressions(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(self.temp.cleanup)
        self.db_patch = patch.object(database, 'DB_PATH', Path(self.temp.name) / 'test.sqlite')
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        self.backup_patch = patch.object(database, 'auto_backup_db')
        self.backup_patch.start()
        self.addCleanup(self.backup_patch.stop)
        self.auth_patch = patch('src.core.caja_manager.AuthManager.require_user', return_value=SimpleNamespace(
            user_id='11111111-1111-4111-8111-111111111111', username='caja1',
            branch_id='f2985c88-2a4e-4e73-92d5-85d905b3db41', role='cajero'))
        self.auth_patch.start()
        self.addCleanup(self.auth_patch.stop)
        database.init_db()
        self.caja_id = CajaManager.abrir_caja(1000)

    def execute(self, sql, params=()):
        with closing(database.get_connection()) as conn:
            with conn:
                cursor = conn.execute(sql, params)
                return cursor.lastrowid

    def sale(self, estado='COMPLETADA', fecha='2026-06-15 12:00:00'):
        return self.execute(
            'INSERT INTO ventas (cliente_id, caja_sesion_id, fecha, subtotal, total, metodo_pago, estado) '
            'VALUES (1, ?, ?, 100, 100, \'EFECTIVO\', ?)',
            (self.caja_id, fecha, estado),
        )

    def test_supplier_cash_payments_reduce_expected_cash_once(self):
        proveedor = self.execute("INSERT INTO proveedores (nombre) VALUES ('Proveedor')")
        CtaCteProveedoresManager.registrar_pago(proveedor, 125, self.caja_id)
        CtaCteProveedoresManager.registrar_pago(proveedor, 75, self.caja_id)
        CtaCteProveedoresManager.registrar_pago(proveedor, 300, self.caja_id, metodo_pago='TRANSFERENCIA')
        CajaManager.registrar_movimiento(self.caja_id, 'EGRESO', 50, 'EFECTIVO')
        resumen = CajaManager.obtener_resumen(self.caja_id)
        self.assertEqual(resumen['egresos_manuales'], 50)
        self.assertEqual(resumen['pagos_proveedor_efectivo'], 200)
        self.assertEqual(resumen['total_efectivo_esperado'], 750)
        self.assertEqual(CtaCteProveedoresManager.get_saldo(proveedor), -500)

    def test_restart_preserves_zero_and_nonzero_historical_costs(self):
        producto = self.execute("INSERT INTO productos (nombre, costo_final) VALUES ('Producto', 10)")
        promo = self.execute("INSERT INTO promociones (nombre, precio_fijo) VALUES ('Combo', 100)")
        self.execute('INSERT INTO promocion_detalles (promocion_id, producto_id, cantidad_requerida) VALUES (?, ?, 2)', (promo, producto))
        venta = self.sale()
        for producto_id, promocion_id, costo in ((producto, None, 0), (producto, None, 7), (None, promo, 0), (None, promo, 13)):
            self.execute('INSERT INTO ventas_detalle (venta_id, producto_id, promocion_id, cantidad, precio_unitario, costo_unitario, subtotal) VALUES (?, ?, ?, 1, 100, ?, 100)', (venta, producto_id, promocion_id, costo))
        self.execute('UPDATE productos SET costo_final = 999 WHERE id = ?', (producto,))
        database.init_db()
        database.init_db()
        with closing(database.get_connection()) as conn:
            costos = [row['costo_unitario'] for row in conn.execute('SELECT costo_unitario FROM ventas_detalle ORDER BY id')]
        self.assertEqual(costos, [0, 7, 0, 13])

    def test_ranking_includes_combos_without_reconstructing_current_contents(self):
        producto = self.execute("INSERT INTO productos (codigo_barras, nombre) VALUES ('123', 'Combo')")
        promo = self.execute("INSERT INTO promociones (nombre, precio_fijo) VALUES ('Combo', 100)")
        venta = self.sale()
        cancelada = self.sale('CANCELADA')
        fuera = self.sale(fecha='2025-01-01 12:00:00')
        for venta_id, producto_id, promo_id, cantidad, subtotal in (
            (venta, producto, None, 2, 40),
            (venta, None, promo, 3, 300),
            (venta, None, promo, 1, 100),
            (venta, None, None, 1, 80),
            (cancelada, None, promo, 99, 9900),
            (fuera, producto, None, 99, 1980),
        ):
            self.execute('INSERT INTO ventas_detalle (venta_id, producto_id, promocion_id, cantidad, precio_unitario, subtotal) VALUES (?, ?, ?, ?, 100, ?)', (venta_id, producto_id, promo_id, cantidad, subtotal))
        rows = ReportesManager.get_productos_mas_vendidos('2026-06-01', '2026-06-30')
        self.assertEqual([(r['nombre'], r['cant_total'], r['recaudacion']) for r in rows], [
            ('PROMO: Combo', 4, 400), ('Combo', 2, 40), ('Combo/Promoción', 1, 80),
        ])
        self.assertEqual(rows[1]['codigo_barras'], '123')


if __name__ == '__main__':
    unittest.main()
