from src.db.database import get_connection

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
    def crear_producto(codigo_barras, nombre, costo_lista, flete, utilidad_porcentaje, precio_contado, precio_tarjeta, stock_actual, stock_minimo, stock_maximo=100.0, categoria_id=None, proveedor_id=None, codigo_fabrica="", unidades_bulto=1, ubicacion="", observaciones=""):
        costo_final = float(costo_lista) + float(flete)
        
        # El código de barras debe ser None si está vacío para evitar problemas de UNIQUE
        codigo_barras = codigo_barras.strip() if codigo_barras and codigo_barras.strip() else None
        
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
            INSERT INTO productos (
                codigo_barras, codigo_fabrica, nombre, costo_lista, flete, costo_final, 
                utilidad_porcentaje, precio_contado, precio_tarjeta, stock_actual, 
                stock_minimo, stock_maximo, unidades_bulto, ubicacion, observaciones,
                categoria_id, proveedor_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (codigo_barras, codigo_fabrica, nombre, costo_lista, flete, costo_final,
                  utilidad_porcentaje, precio_contado, precio_tarjeta, stock_actual,
                  stock_minimo, stock_maximo, unidades_bulto, ubicacion, observaciones,
                  categoria_id, proveedor_id))
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def actualizar_producto(producto_id, codigo_barras, nombre, costo_lista, flete, utilidad_porcentaje, precio_contado, precio_tarjeta, stock_actual, stock_minimo, stock_maximo=100.0, categoria_id=None, proveedor_id=None, codigo_fabrica="", unidades_bulto=1, ubicacion="", observaciones=""):
        costo_final = float(costo_lista) + float(flete)
        codigo_barras = codigo_barras.strip() if codigo_barras and codigo_barras.strip() else None
        
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
            UPDATE productos SET 
                codigo_barras = ?, codigo_fabrica = ?, nombre = ?, costo_lista = ?, flete = ?, 
                costo_final = ?, utilidad_porcentaje = ?, precio_contado = ?, precio_tarjeta = ?, 
                stock_actual = ?, stock_minimo = ?, stock_maximo = ?, unidades_bulto = ?, 
                ubicacion = ?, observaciones = ?, categoria_id = ?, proveedor_id = ?
            WHERE id = ?
            """, (codigo_barras, codigo_fabrica, nombre, costo_lista, flete, costo_final,
                  utilidad_porcentaje, precio_contado, precio_tarjeta, stock_actual,
                  stock_minimo, stock_maximo, unidades_bulto, ubicacion, observaciones,
                  categoria_id, proveedor_id, producto_id))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def eliminar_producto(producto_id):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE productos SET activo = 0 WHERE id = ?", (producto_id,))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def restaurar_producto(producto_id):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE productos SET activo = 1 WHERE id = ?", (producto_id,))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def actualizar_stock(producto_id, cantidad_cambio):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE productos SET stock_actual = stock_actual + ? WHERE id = ?", (cantidad_cambio, producto_id))
        conn.commit()
        conn.close()

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
