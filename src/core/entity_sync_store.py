"""Captura transaccional de productos/ventas y aplicación idempotente de precios."""
from contextlib import closing
import json
import math
import uuid

from src.core.auth_manager import AuthManager
from src.db.database import get_connection


class EntitySyncStore:
    INITIAL_BATCH_SIZE = 200

    @staticmethod
    def merge_catalog(user, products):
        fields = ('codigo_barras', 'codigo_fabrica', 'nombre', 'ubicacion', 'observaciones')
        numbers = ('costo_lista', 'flete', 'costo_final', 'utilidad_porcentaje', 'precio_contado',
                   'precio_tarjeta', 'stock_actual', 'stock_minimo', 'stock_maximo', 'unidades_bulto')
        columns = (*fields, *numbers, 'activo', 'categoria_id', 'proveedor_id',
                   'sync_id', 'sync_revision', 'catalog_revision')
        placeholders = ','.join('?' for _ in columns)
        assignments = ','.join(f'{column}=?' for column in columns)
        conflicts = set()
        changed = False
        with closing(get_connection()) as conn, conn:
            conn.execute('BEGIN IMMEDIATE')
            EntitySyncStore._bind(conn, user)
            for product in products:
                local = conn.execute('SELECT id,sync_revision FROM productos WHERE sync_id=?',
                                     (product['id'],)).fetchone()
                if local and (local['sync_revision'] >= product['revision'] or conn.execute(
                    "SELECT 1 FROM sync_entidades WHERE sucursal_id=? AND tipo='PRODUCTO' "
                    "AND entidad_id=? AND estado='PENDIENTE'",
                    (user.branch_id, product['id']),
                ).fetchone()):
                    continue
                barcode = product['codigo_barras']
                if barcode is not None and conn.execute(
                    'SELECT 1 FROM productos WHERE codigo_barras=? AND id<>?',
                    (barcode, local['id'] if local else -1),
                ).fetchone():
                    conflicts.add(barcode or '(vacío)')
                    continue
                category_id = None
                supplier_id = None
                category = product.get('categoria_nombre')
                if category:
                    conn.execute('INSERT OR IGNORE INTO categorias(nombre) VALUES (?)', (category,))
                    category_id = conn.execute('SELECT id FROM categorias WHERE nombre=?', (category,)).fetchone()['id']
                supplier = product.get('proveedor_nombre')
                if supplier:
                    existing = conn.execute('SELECT id FROM proveedores WHERE nombre=? ORDER BY id LIMIT 1',
                                            (supplier,)).fetchone()
                    supplier_id = existing['id'] if existing else conn.execute(
                        'INSERT INTO proveedores(nombre) VALUES (?)', (supplier,)).lastrowid
                values = (*(product[field] for field in fields),
                          *(EntitySyncStore._number(product[field], field) for field in numbers),
                          product['activo'], category_id, supplier_id, product['id'],
                          product['revision'], product['catalog_revision'])
                if local:
                    conn.execute(f'UPDATE productos SET {assignments} WHERE id=?', (*values, local['id']))
                else:
                    conn.execute(f"INSERT INTO productos ({','.join(columns)}) VALUES ({placeholders})", values)
                changed = True
        return changed, conflicts

    @staticmethod
    def _actor(user):
        actual = AuthManager.require_user()
        if (actual.user_id, actual.branch_id) != (user.user_id, user.branch_id):
            raise ValueError('La sesión cambió durante la operación. Ingrese nuevamente.')
        if actual.role not in ('cajero', 'admin'):
            raise ValueError('El usuario no está habilitado para esta operación.')

    @staticmethod
    def _bind(conn, user):
        EntitySyncStore._actor(user)
        binding = conn.execute("SELECT value FROM sync_configuracion WHERE key = 'sucursal_id'").fetchone()
        if binding and binding['value'] != user.branch_id:
            raise ValueError('La base local ya está vinculada a otra sucursal. No se pueden mezclar sus datos.')
        foreign = conn.execute("SELECT 1 FROM caja_sesiones WHERE sucursal_id IS NOT NULL AND sucursal_id <> ? LIMIT 1", (user.branch_id,)).fetchone()
        if foreign:
            raise ValueError('La base local contiene turnos de otra sucursal. Revise la instalación.')
        if not binding:
            conn.execute("INSERT INTO sync_configuracion(key, value) VALUES ('sucursal_id', ?)", (user.branch_id,))

    @staticmethod
    def _uuid(conn, table, local_id):
        # table solo procede de literales internos, nunca de una petición remota.
        row = conn.execute(f'SELECT sync_id FROM {table} WHERE id = ?', (local_id,)).fetchone()
        if row is None:
            raise ValueError(f'No se encontró el registro local {local_id} de {table}.')
        if row['sync_id']:
            return row['sync_id']
        identity = str(uuid.uuid4())
        conn.execute(f'UPDATE {table} SET sync_id = ? WHERE id = ?', (identity, local_id))
        return identity

    @staticmethod
    def _number(value, field):
        try:
            result = float(value)
        except (ValueError, TypeError, OverflowError):
            raise ValueError(f'El campo {field} debe ser un número finito.') from None
        if not math.isfinite(result):
            raise ValueError(f'El campo {field} debe ser un número finito.')
        return result

    @staticmethod
    def _enqueue(conn, user, kind, payload, owner_id=None):
        conn.execute("""
            INSERT INTO sync_entidades(id, sucursal_id, usuario_id, tipo, entidad_id, revision, payload)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (str(uuid.uuid4()), user.branch_id, owner_id or user.user_id, kind, payload['id'], payload['revision'],
              json.dumps(payload, ensure_ascii=False, allow_nan=False)))

    @staticmethod
    def queue_product(conn, product_id, user, catalog_changed=True):
        """La conexión del negocio conserva responsabilidad sobre commit/rollback."""
        EntitySyncStore._bind(conn, user)
        identity = EntitySyncStore._uuid(conn, 'productos', product_id)
        conn.execute("""
            UPDATE productos SET sync_revision = sync_revision + 1,
                catalog_revision = catalog_revision + CASE WHEN ? OR sync_revision = 0 THEN 1 ELSE 0 END
            WHERE id = ?
        """, (bool(catalog_changed), product_id))
        row = conn.execute("""
            SELECT p.*, c.nombre AS categoria_nombre, pr.nombre AS proveedor_nombre
            FROM productos p LEFT JOIN categorias c ON c.id = p.categoria_id
            LEFT JOIN proveedores pr ON pr.id = p.proveedor_id WHERE p.id = ?
        """, (product_id,)).fetchone()
        payload = {
            'id': identity, 'sucursal_id': user.branch_id, 'revision': row['sync_revision'],
            'catalog_revision': row['catalog_revision'], 'local_id': row['id'],
        }
        for field in ('codigo_barras', 'codigo_fabrica', 'nombre', 'ubicacion', 'observaciones',
                      'categoria_nombre', 'proveedor_nombre'):
            payload[field] = row[field]
        for field in ('costo_lista', 'flete', 'costo_final', 'utilidad_porcentaje', 'precio_contado',
                      'precio_tarjeta', 'stock_actual', 'stock_minimo', 'stock_maximo', 'unidades_bulto'):
            payload[field] = EntitySyncStore._number(row[field], f"{field} del producto #{row['id']} ({row['nombre']})")
            if abs(payload[field]) >= 100_000_000_000_000:
                raise ValueError(f"El campo {field} del producto #{row['id']} está fuera del rango admitido para sincronizar.")
        if not isinstance(payload['nombre'], str) or not payload['nombre'].strip():
            raise ValueError(f"El producto #{row['id']} no tiene un nombre válido. Corríjalo antes de sincronizar.")
        if payload['precio_contado'] < 0 or payload['precio_tarjeta'] < 0:
            raise ValueError(f"El producto #{row['id']} ({row['nombre']}) tiene precios negativos. Corríjalos antes de sincronizar; sus datos no se modificaron.")
        payload['activo'] = bool(row['activo'])
        EntitySyncStore._enqueue(conn, user, 'PRODUCTO', payload)
        return payload

    @staticmethod
    def queue_sale(conn, sale_id, user, items=None):
        EntitySyncStore._bind(conn, user)
        identity = EntitySyncStore._uuid(conn, 'ventas', sale_id)
        sale = conn.execute("""
            SELECT v.*, strftime('%Y-%m-%dT%H:%M:%SZ', v.fecha) AS sold_at,
                   c.nombre AS cliente_nombre, cs.sync_id AS caja_sync_id
            FROM ventas v LEFT JOIN clientes c ON c.id = v.cliente_id
            LEFT JOIN caja_sesiones cs ON cs.id = v.caja_sesion_id WHERE v.id = ?
        """, (sale_id,)).fetchone()
        if not sale['sold_at']:
            raise ValueError('La fecha de la venta no es válida para sincronizar.')
        details = conn.execute("""
            SELECT vd.*, p.nombre AS producto_nombre, pr.nombre AS promocion_nombre
            FROM ventas_detalle vd LEFT JOIN productos p ON p.id = vd.producto_id
            LEFT JOIN promociones pr ON pr.id = vd.promocion_id
            WHERE vd.venta_id = ? ORDER BY vd.id
        """, (sale_id,)).fetchall()
        if items is not None and len(items) != len(details):
            raise ValueError('El detalle de la venta no coincide con el carrito registrado.')
        historical = sale['vendedor_id'] is None
        if not historical and sale['vendedor_id'] != user.user_id and user.role != 'admin':
            raise ValueError('Solo el vendedor original o un administrador de la sucursal puede capturar esta venta.')
        snapshot_details = []
        for position, row in enumerate(details):
            product_uuid = EntitySyncStore._uuid(conn, 'productos', row['producto_id']) if row['producto_id'] is not None else None
            name = row['nombre_sync']
            components = json.loads(row['componentes_sync']) if row['componentes_sync'] else []
            if name is None and items is not None:
                item = items[position]
                name = row['producto_nombre'] or ('PROMO: ' + row['promocion_nombre'] if row['promocion_nombre'] else 'Combo/Promoción')
                if item.get('es_promo'):
                    for component in item['detalles']:
                        component_row = conn.execute('SELECT nombre FROM productos WHERE id = ?', (component['producto_id'],)).fetchone()
                        if component_row is None:
                            raise ValueError('Un producto de la promoción no existe.')
                        components.append({
                            'producto_id': EntitySyncStore._uuid(conn, 'productos', component['producto_id']),
                            'nombre': component_row['nombre'],
                            'cantidad_requerida': EntitySyncStore._number(component['cantidad_requerida'], 'cantidad_requerida'),
                        })
                conn.execute('UPDATE ventas_detalle SET nombre_sync = ?, componentes_sync = ? WHERE id = ?',
                             (name, json.dumps(components, ensure_ascii=False, allow_nan=False), row['id']))
            if name is None:
                # El esquema antiguo no guardaba nombres/componentes históricos.
                # Mostrar el nombre actual etiquetado, sin afirmar que era el original.
                current_name = row['producto_nombre'] or row['promocion_nombre'] or 'Combo/Promoción'
                name = f'{current_name} (nombre actual; venta histórica)'
            detail = {
                'producto_id': product_uuid, 'promocion_id': row['promocion_id'], 'nombre': name,
                'componentes': components,
            }
            for field in ('cantidad', 'precio_unitario', 'costo_unitario', 'subtotal'):
                detail[field] = EntitySyncStore._number(row[field], field)
            snapshot_details.append(detail)
        conn.execute('UPDATE ventas SET sync_revision = sync_revision + 1 WHERE id = ?', (sale_id,))
        revision = sale['sync_revision'] + 1
        payload = {
            'id': identity, 'sucursal_id': user.branch_id, 'revision': revision, 'local_id': sale['id'],
            'fecha': sale['sold_at'], 'estado': sale['estado'], 'cliente_nombre': sale['cliente_nombre'],
            'metodo_pago': sale['metodo_pago'], 'caja_sync_id': sale['caja_sync_id'],
            'vendedor_id': sale['vendedor_id'], 'historica': historical, 'detalles': snapshot_details,
            'responsable_nombre': sale['vendedor_nombre'],
        }
        for field in ('subtotal', 'descuento_total', 'total'):
            payload[field] = EntitySyncStore._number(sale[field], field)
            if payload[field] < 0 or payload[field] >= 100_000_000_000_000:
                raise ValueError(f'El campo {field} de la venta #{sale_id} está fuera del rango admitido para sincronizar; no se modificó el histórico.')
        EntitySyncStore._enqueue(conn, user, 'VENTA', payload, owner_id=sale['vendedor_id'])
        return payload

    @staticmethod
    def validate_installation(user):
        """Valida/establece el vínculo sin depender de la calidad de datos históricos."""
        with closing(get_connection()) as conn:
            with conn:
                conn.execute('BEGIN IMMEDIATE')
                EntitySyncStore._bind(conn, user)

    @staticmethod
    def prepare_initial_sync(user):
        """Importación inicial por lotes; revision=0 es el cursor durable, no un hash."""
        with closing(get_connection()) as conn:
            with conn:
                conn.execute('BEGIN IMMEDIATE')
                EntitySyncStore._bind(conn, user)
                products = conn.execute('SELECT id FROM productos WHERE sync_revision = 0 ORDER BY id LIMIT ?',
                                        (EntitySyncStore.INITIAL_BATCH_SIZE,)).fetchall()
                for row in products:
                    EntitySyncStore.queue_product(conn, row['id'], user)
                remaining = EntitySyncStore.INITIAL_BATCH_SIZE - len(products)
                if remaining:
                    sales = conn.execute('SELECT id FROM ventas WHERE sync_revision = 0 ORDER BY id LIMIT ?',
                                         (remaining,)).fetchall()
                    for row in sales:
                        EntitySyncStore.queue_sale(conn, row['id'], user)

    @staticmethod
    def initial_pending_count(user=None):
        user = user or AuthManager.current_user()
        if user is None:
            return 0
        with closing(get_connection()) as conn:
            bound = conn.execute("SELECT value FROM sync_configuracion WHERE key = 'sucursal_id'").fetchone()
            if bound and bound['value'] != user.branch_id:
                raise ValueError('La base local está vinculada a otra sucursal.')
            return conn.execute('SELECT (SELECT COUNT(*) FROM productos WHERE sync_revision = 0) + (SELECT COUNT(*) FROM ventas WHERE sync_revision = 0) AS n').fetchone()['n']

    @staticmethod
    def apply_price_command(command, user):
        EntitySyncStore._actor(user)
        if command.get('sucursal_id') != user.branch_id:
            raise ValueError('La orden de precios pertenece a otra sucursal.')
        try:
            command_id = str(uuid.UUID(command['id']))
            product_id = str(uuid.UUID(command['producto_id']))
        except (ValueError, KeyError, TypeError, AttributeError):
            raise ValueError('La orden de precios tiene identificadores inválidos.') from None
        expected = command.get('expected_catalog_revision')
        if isinstance(expected, bool) or not isinstance(expected, int) or expected <= 0:
            raise ValueError('La revisión esperada debe ser un entero positivo.')
        contado = EntitySyncStore._number(command.get('precio_contado'), 'precio_contado')
        tarjeta = EntitySyncStore._number(command.get('precio_tarjeta'), 'precio_tarjeta')
        if contado < 0 or tarjeta < 0:
            raise ValueError('Los precios no pueden ser negativos.')
        if contado >= 100_000_000_000_000 or tarjeta >= 100_000_000_000_000:
            raise ValueError('Los precios están fuera del rango admitido para sincronizar.')
        with closing(get_connection()) as conn:
            with conn:
                conn.execute('BEGIN IMMEDIATE')
                EntitySyncStore._bind(conn, user)
                receipt = conn.execute('SELECT resultado FROM sync_comandos_aplicados WHERE id = ?', (command_id,)).fetchone()
                if receipt:
                    return json.loads(receipt['resultado'])
                product = conn.execute('SELECT id, catalog_revision FROM productos WHERE sync_id = ?', (product_id,)).fetchone()
                result = {'command_id': command_id, 'status': None, 'detail': None}
                if product is None:
                    result.update(status='NO_ENCONTRADO', detail='El producto no existe en esta instalación.')
                elif product['catalog_revision'] != expected:
                    result.update(status='CONFLICTO', detail=f"El catálogo cambió localmente: revisión actual {product['catalog_revision']}, esperada {expected}.")
                else:
                    conn.execute('UPDATE productos SET precio_contado = ?, precio_tarjeta = ? WHERE id = ?',
                                 (contado, tarjeta, product['id']))
                    updated = EntitySyncStore.queue_product(conn, product['id'], user, catalog_changed=True)
                    result.update(status='APLICADO', detail=f"Precios actualizados. Revisión de catálogo {updated['catalog_revision']}.")
                conn.execute('INSERT INTO sync_comandos_aplicados(id, estado, resultado) VALUES (?, ?, ?)',
                             (command_id, result['status'], json.dumps(result, ensure_ascii=False, allow_nan=False)))
                return result
