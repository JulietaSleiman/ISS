from src.db.database import get_connection
from src.core.caja_manager import CajaManager
from src.core.productos_manager import ProductosManager
from src.core.auth_manager import AuthManager
from src.core.entity_sync_store import EntitySyncStore

class VentasManager:
    @staticmethod
    def procesar_venta(cliente_id: int, metodo_pago: str, carrito: list, montos_mixto: dict = None):
        """
        carrito: list of dicts con {'producto_id': int, 'cantidad': int, 'precio_unitario': float}
        Procesa la venta atómicamente: registra venta, detalles, actualiza stock y caja.
        """
        user = AuthManager.require_user()
        sesion_caja = CajaManager.obtener_sesion_activa()
        if not sesion_caja:
            raise Exception("Debe abrir la caja antes de realizar una venta.")

        if not carrito:
            raise ValueError('Agregue al menos un producto antes de registrar la venta.')
        validated = []
        touched_products = set()

        def product_identity(value):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError('El identificador del producto no es válido.')
            return value

        for original in carrito:
            item = dict(original)
            item['cantidad'] = EntitySyncStore._number(item.get('cantidad'), 'cantidad')
            item['precio_unitario'] = EntitySyncStore._number(item.get('precio_unitario'), 'precio_unitario')
            if item['cantidad'] <= 0 or item['precio_unitario'] < 0:
                raise ValueError('La cantidad debe ser positiva y el precio no puede ser negativo.')
            if item.get('es_promo'):
                if not item.get('detalles'):
                    raise ValueError('La promoción debe contener productos.')
                item['detalles'] = [dict(component) for component in item['detalles']]
                for component in item['detalles']:
                    component['producto_id'] = product_identity(component.get('producto_id'))
                    component['cantidad_requerida'] = EntitySyncStore._number(component.get('cantidad_requerida'), 'cantidad_requerida')
                    if component['cantidad_requerida'] <= 0:
                        raise ValueError('Las cantidades de una promoción deben ser positivas.')
                    touched_products.add(component['producto_id'])
            else:
                item['producto_id'] = product_identity(item.get('producto_id'))
                touched_products.add(item['producto_id'])
            validated.append(item)
        carrito = validated
        subtotal = sum(item['cantidad'] * item['precio_unitario'] for item in carrito)
        EntitySyncStore._number(subtotal, 'subtotal')
        
        # Calcular descuento si aplica según el cliente
        descuento_total = 0.0
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('BEGIN IMMEDIATE')
            EntitySyncStore._bind(conn, user)
            sesion_caja = CajaManager._activa(conn, user)
            if not sesion_caja:
                raise ValueError('La caja ya no está abierta.')
            costs = {}
            for product_id in touched_products:
                product = cursor.execute('SELECT costo_final FROM productos WHERE id = ?', (product_id,)).fetchone()
                if product is None:
                    raise ValueError('Uno de los productos de la venta ya no existe.')
                cost = EntitySyncStore._number(product['costo_final'], 'costo_final')
                if cost < 0:
                    raise ValueError('El costo del producto no puede ser negativo.')
                costs[product_id] = cost
            cursor.execute("SELECT descuento_porcentaje FROM clientes WHERE id = ?", (cliente_id,))
            cliente = cursor.fetchone()
            if cliente:
                discount = EntitySyncStore._number(cliente['descuento_porcentaje'], 'descuento_porcentaje')
                if not 0 <= discount <= 100:
                    raise ValueError('El descuento del cliente debe estar entre 0 y 100 por ciento.')
                descuento_total = subtotal * (discount / 100.0)
            
            total = subtotal - descuento_total
            EntitySyncStore._number(total, 'total')

            # 1. Crear registro de venta
            cursor.execute("""
            INSERT INTO ventas (cliente_id, caja_sesion_id, subtotal, descuento_total, total, metodo_pago, vendedor_id, vendedor_nombre)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (cliente_id, sesion_caja['id'], subtotal, descuento_total, total, metodo_pago, user.user_id, user.username))
            
            venta_id = cursor.lastrowid

            # 2. Registrar detalles y descontar stock
            for item in carrito:
                if item.get('es_promo'):
                    # Es un combo. Guardamos la línea de venta como la promo.
                    
                    # Calcular el costo total de la promo en base a sus productos
                    costo_promo = 0.0
                    for det in item['detalles']:
                        c_final = costs[det['producto_id']]
                        costo_promo += c_final * det['cantidad_requerida']
                    EntitySyncStore._number(costo_promo, 'costo_promo')

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
                    costo_unit = costs[item['producto_id']]

                    cursor.execute("""
                    INSERT INTO ventas_detalle (venta_id, producto_id, cantidad, precio_unitario, costo_unitario, subtotal)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """, (venta_id, item['producto_id'], item['cantidad'], item['precio_unitario'], costo_unit, subt_item))
                    
                    # La política existente permite stock negativo; sí se captura su saldo final.
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

            # Una instantánea final por producto tocado, aunque se repita en varios
            # renglones o combos. El fallo de captura revierte venta, caja y stock.
            for product_id in sorted(touched_products):
                EntitySyncStore.queue_product(conn, product_id, user, catalog_changed=False)
            EntitySyncStore.queue_sale(conn, venta_id, user, items=carrito)
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
