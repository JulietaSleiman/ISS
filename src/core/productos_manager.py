from contextlib import closing

from src.db.database import get_connection
from src.core.auth_manager import AuthManager
from src.core.entity_sync_store import EntitySyncStore

class ProductosManager:
    @staticmethod
    def calcular_precios(costo_lista: float, flete: float, utilidad_porcentaje: float):
        """Calcula el costo final y precios basado en los parámetros."""
        costo_final = costo_lista + flete
        precio_contado = costo_final + (costo_final * (utilidad_porcentaje / 100))
        return costo_final, precio_contado

    @staticmethod
    def get_all(incluir_inactivos=False):
        conn = get_connection()
        cursor = conn.cursor()
        query = "SELECT p.*, c.nombre as categoria_nombre, pr.nombre as proveedor_nombre FROM productos p LEFT JOIN categorias c ON p.categoria_id = c.id LEFT JOIN proveedores pr ON p.proveedor_id = pr.id"
        if not incluir_inactivos:
            query += " WHERE p.activo = 1"
        cursor.execute(query)
        productos = cursor.fetchall()
        conn.close()
        return productos

    @staticmethod
    def get_by_codigo(codigo: str):
        conn = get_connection()
        cursor = conn.cursor()
        
        # Primero intentar por código de barras
        cursor.execute("SELECT * FROM productos WHERE codigo_barras = ? AND activo = 1", (codigo,))
        producto = cursor.fetchone()
        
        # Si no se encuentra y es numérico, intentar por código interno (id)
        if not producto and codigo and codigo.isdigit():
            cursor.execute("SELECT * FROM productos WHERE id = ? AND activo = 1", (int(codigo),))
            producto = cursor.fetchone()
            
        conn.close()
        return producto

    @staticmethod
    def get_by_id(producto_id: int):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM productos WHERE id = ?", (producto_id,))
        producto = cursor.fetchone()
        conn.close()
        return producto

    @staticmethod
    def _valores(codigo_barras, nombre, costo_lista, flete, utilidad_porcentaje,
                 precio_contado, precio_tarjeta, stock_actual, stock_minimo, stock_maximo,
                 categoria_id, proveedor_id, codigo_fabrica, unidades_bulto, ubicacion, observaciones):
        if not isinstance(nombre, str) or not nombre.strip():
            raise ValueError("Ingrese el nombre del producto.")
        values = {
            'codigo_barras': codigo_barras.strip() if codigo_barras and codigo_barras.strip() else None,
            'codigo_fabrica': codigo_fabrica, 'nombre': nombre.strip(),
            'categoria_id': categoria_id, 'proveedor_id': proveedor_id,
            'unidades_bulto': unidades_bulto, 'ubicacion': ubicacion, 'observaciones': observaciones,
        }
        for field, value in (
            ('costo_lista', costo_lista), ('flete', flete), ('utilidad_porcentaje', utilidad_porcentaje),
            ('precio_contado', precio_contado), ('precio_tarjeta', precio_tarjeta),
            ('stock_actual', stock_actual), ('stock_minimo', stock_minimo), ('stock_maximo', stock_maximo),
        ):
            values[field] = EntitySyncStore._number(value, field)
        values['costo_final'] = EntitySyncStore._number(values['costo_lista'] + values['flete'], 'costo_final')
        if values['precio_contado'] < 0 or values['precio_tarjeta'] < 0:
            raise ValueError('Los precios de contado y tarjeta no pueden ser negativos.')
        return values

    @staticmethod
    def crear_producto(codigo_barras, nombre, costo_lista, flete, utilidad_porcentaje, precio_contado, precio_tarjeta, stock_actual, stock_minimo, stock_maximo=100.0, categoria_id=None, proveedor_id=None, codigo_fabrica="", unidades_bulto=1, ubicacion="", observaciones=""):
        user = AuthManager.require_user()
        values = ProductosManager._valores(codigo_barras, nombre, costo_lista, flete, utilidad_porcentaje,
            precio_contado, precio_tarjeta, stock_actual, stock_minimo, stock_maximo,
            categoria_id, proveedor_id, codigo_fabrica, unidades_bulto, ubicacion, observaciones)
        with closing(get_connection()) as conn:
            with conn:
                conn.execute('BEGIN IMMEDIATE')
                EntitySyncStore._bind(conn, user)
                fields = ', '.join(values)
                placeholders = ', '.join('?' for _ in values)
                cursor = conn.execute(f'INSERT INTO productos ({fields}) VALUES ({placeholders})', tuple(values.values()))
                product_id = cursor.lastrowid
                EntitySyncStore.queue_product(conn, product_id, user)
                return product_id

    @staticmethod
    def actualizar_producto(producto_id, codigo_barras, nombre, costo_lista, flete, utilidad_porcentaje, precio_contado, precio_tarjeta, stock_actual, stock_minimo, stock_maximo=100.0, categoria_id=None, proveedor_id=None, codigo_fabrica="", unidades_bulto=1, ubicacion="", observaciones=""):
        user = AuthManager.require_user()
        values = ProductosManager._valores(codigo_barras, nombre, costo_lista, flete, utilidad_porcentaje,
            precio_contado, precio_tarjeta, stock_actual, stock_minimo, stock_maximo,
            categoria_id, proveedor_id, codigo_fabrica, unidades_bulto, ubicacion, observaciones)
        with closing(get_connection()) as conn:
            with conn:
                conn.execute('BEGIN IMMEDIATE')
                EntitySyncStore._bind(conn, user)
                previous = conn.execute('SELECT * FROM productos WHERE id = ?', (producto_id,)).fetchone()
                if previous is None:
                    raise ValueError('No se encontró el producto.')
                changed = [field for field, value in values.items() if previous[field] != value]
                if not changed:
                    return True
                conn.execute('UPDATE productos SET ' + ', '.join(field + ' = ?' for field in values) + ' WHERE id = ?',
                             (*values.values(), producto_id))
                EntitySyncStore.queue_product(conn, producto_id, user, catalog_changed=any(field != 'stock_actual' for field in changed))
                return True

    @staticmethod
    def _cambiar_estado(producto_id, activo):
        user = AuthManager.require_user()
        with closing(get_connection()) as conn:
            with conn:
                conn.execute('BEGIN IMMEDIATE')
                EntitySyncStore._bind(conn, user)
                previous = conn.execute('SELECT activo FROM productos WHERE id = ?', (producto_id,)).fetchone()
                if previous is None:
                    raise ValueError('No se encontró el producto.')
                if bool(previous['activo']) == bool(activo):
                    return True
                conn.execute('UPDATE productos SET activo = ? WHERE id = ?', (int(activo), producto_id))
                EntitySyncStore.queue_product(conn, producto_id, user)
                return True

    @staticmethod
    def eliminar_producto(producto_id):
        return ProductosManager._cambiar_estado(producto_id, False)

    @staticmethod
    def restaurar_producto(producto_id):
        return ProductosManager._cambiar_estado(producto_id, True)

    @staticmethod
    def actualizar_stock(producto_id, cantidad_cambio):
        user = AuthManager.require_user()
        delta = EntitySyncStore._number(cantidad_cambio, 'cantidad_cambio')
        with closing(get_connection()) as conn:
            with conn:
                conn.execute('BEGIN IMMEDIATE')
                EntitySyncStore._bind(conn, user)
                product = conn.execute('SELECT id FROM productos WHERE id = ?', (producto_id,)).fetchone()
                if product is None:
                    raise ValueError('No se encontró el producto.')
                if delta == 0:
                    return
                conn.execute('UPDATE productos SET stock_actual = stock_actual + ? WHERE id = ?', (delta, producto_id))
                EntitySyncStore.queue_product(conn, producto_id, user, catalog_changed=False)

    @staticmethod
    def get_historial_producto(producto_id: int):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                v.fecha,
                COALESCE(c.nombre, 'Consumidor Final') as cliente,
                vd.cantidad,
                vd.precio_unitario,
                vd.subtotal,
                v.metodo_pago
            FROM ventas_detalle vd
            JOIN ventas v ON vd.venta_id = v.id
            LEFT JOIN clientes c ON v.cliente_id = c.id
            WHERE vd.producto_id = ? AND v.estado != 'CANCELADA'
            ORDER BY v.fecha DESC
        """, (producto_id,))
        historial = cursor.fetchall()
        conn.close()
        return historial
