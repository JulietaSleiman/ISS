from src.db.database import get_connection
from src.core.caja_manager import CajaManager
from src.core.productos_manager import ProductosManager

class VentasManager:
    @staticmethod
    def procesar_venta(cliente_id: int, metodo_pago: str, carrito: list, montos_mixto: dict = None):
        """
        carrito: list of dicts con {'producto_id': int, 'cantidad': int, 'precio_unitario': float}
        Procesa la venta atómicamente: registra venta, detalles, actualiza stock y caja.
        """
        sesion_caja = CajaManager.obtener_sesion_activa()
        if not sesion_caja:
            raise Exception("Debe abrir la caja antes de realizar una venta.")

        subtotal = sum(item['cantidad'] * item['precio_unitario'] for item in carrito)
        
        # Calcular descuento si aplica según el cliente
        descuento_total = 0.0
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            # Transacción iniciada automáticamente
            cursor.execute("SELECT descuento_porcentaje FROM clientes WHERE id = ?", (cliente_id,))
            cliente = cursor.fetchone()
            if cliente and cliente['descuento_porcentaje'] > 0:
                descuento_total = subtotal * (cliente['descuento_porcentaje'] / 100.0)
            
            total = subtotal - descuento_total

            # 1. Crear registro de venta
            cursor.execute("""
            INSERT INTO ventas (cliente_id, caja_sesion_id, subtotal, descuento_total, total, metodo_pago)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (cliente_id, sesion_caja['id'], subtotal, descuento_total, total, metodo_pago))
            
            venta_id = cursor.lastrowid

            # 2. Registrar detalles y descontar stock
            for item in carrito:
                if item.get('es_promo'):
                    # Es un combo. Guardamos la línea de venta como la promo.
                    
                    # Calcular el costo total de la promo en base a sus productos
                    costo_promo = 0.0
                    for det in item['detalles']:
                        cursor.execute("SELECT costo_final FROM productos WHERE id = ?", (det['producto_id'],))
                        prod_cost = cursor.fetchone()
                        c_final = prod_cost['costo_final'] if prod_cost else 0.0
                        costo_promo += c_final * det['cantidad_requerida']

                    cursor.execute("""
                    INSERT INTO ventas_detalle (venta_id, producto_id, promocion_id, cantidad, precio_unitario, costo_unitario, subtotal)
                    VALUES (?, NULL, ?, ?, ?, ?, ?)
                    """, (venta_id, item.get('promocion_id'), item['cantidad'], item['precio_unitario'], costo_promo, item['cantidad'] * item['precio_unitario']))
                    
                    # Descontamos el stock de cada producto que compone la promo
                    for det in item['detalles']:
                        cant_total_a_descontar = det['cantidad_requerida'] * item['cantidad']
                        cursor.execute("UPDATE productos SET stock_actual = stock_actual - ? WHERE id = ?", 
                                       (cant_total_a_descontar, det['producto_id']))
                else:
                    subt_item = item['cantidad'] * item['precio_unitario']
                    
                    # Obtener costo_final del producto
                    cursor.execute("SELECT costo_final FROM productos WHERE id = ?", (item['producto_id'],))
                    prod_cost = cursor.fetchone()
                    costo_unit = prod_cost['costo_final'] if prod_cost else 0.0

                    cursor.execute("""
                    INSERT INTO ventas_detalle (venta_id, producto_id, cantidad, precio_unitario, costo_unitario, subtotal)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """, (venta_id, item['producto_id'], item['cantidad'], item['precio_unitario'], costo_unit, subt_item))
                    
                    # Validar y descontar stock
                    cursor.execute("SELECT stock_actual FROM productos WHERE id = ?", (item['producto_id'],))
                    prod_db = cursor.fetchone()
                    
                    cursor.execute("""
                    UPDATE productos SET stock_actual = stock_actual - ? WHERE id = ?
                    """, (item['cantidad'], item['producto_id']))

            # 3. Registrar en movimientos de caja (opcional, para tener el flujo de ingresos detallado)
            if metodo_pago == 'MIXTO' and montos_mixto:
                for mp, monto in montos_mixto.items():
                    if monto > 0:
                        cursor.execute("""
                        INSERT INTO caja_movimientos (caja_sesion_id, tipo, monto, metodo_pago, descripcion)
                        VALUES (?, 'VENTA', ?, ?, ?)
                        """, (sesion_caja['id'], monto, mp, f"Venta #{venta_id} (Mixto)"))
            elif metodo_pago != 'FIADO / CTA. CTE.':
                cursor.execute("""
                INSERT INTO caja_movimientos (caja_sesion_id, tipo, monto, metodo_pago, descripcion)
                VALUES (?, 'VENTA', ?, ?, ?)
                """, (sesion_caja['id'], total, metodo_pago, f"Venta #{venta_id}"))
            else:
                # Registrar deuda en Cta Cte
                cursor.execute("""
                INSERT INTO cta_cte_movimientos (cliente_id, caja_sesion_id, venta_id, tipo, monto, detalle)
                VALUES (?, ?, ?, 'DEUDA', ?, ?)
                """, (cliente_id, sesion_caja['id'], venta_id, total, f"Venta Fiada #{venta_id}"))

            conn.commit()
            return {
                "venta_id": venta_id,
                "subtotal": subtotal,
                "descuento": descuento_total,
                "total": total
            }

        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def get_detalles_venta(venta_id: int):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.nombre AS producto_nombre, pr.nombre AS promo_nombre, vd.cantidad, vd.precio_unitario, vd.subtotal
            FROM ventas_detalle vd
            LEFT JOIN productos p ON vd.producto_id = p.id
            LEFT JOIN promociones pr ON vd.promocion_id = pr.id
            WHERE vd.venta_id = ?
        """, (venta_id,))
        detalles = cursor.fetchall()
        conn.close()
        
        resultado = []
        for d in detalles:
            nombre = d['producto_nombre']
            if not nombre:
                nombre = "PROMO: " + d['promo_nombre'] if d['promo_nombre'] else 'Combo/Promoción'
            resultado.append({
                'nombre': nombre,
                'cantidad': d['cantidad'],
                'precio_unitario': d['precio_unitario'],
                'subtotal': d['subtotal']
            })
                
        return resultado
