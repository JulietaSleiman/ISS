import sqlite3
from src.db.database import get_connection

class ReportesManager:
    @staticmethod
    def get_ventas_por_fecha(fecha_desde: str, fecha_hasta: str, metodo_pago: str = None):
        desde = f"{fecha_desde} 00:00:00"
        hasta = f"{fecha_hasta} 23:59:59"
        
        conn = get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT v.id, v.fecha, v.total, v.metodo_pago, c.nombre as cliente
            FROM ventas v
            LEFT JOIN clientes c ON v.cliente_id = c.id
            WHERE v.estado != 'CANCELADA' AND datetime(v.fecha, 'localtime') BETWEEN ? AND ?
        """
        params = [desde, hasta]
        
        if metodo_pago:
            query += " AND v.metodo_pago = ?"
            params.append(metodo_pago)
            
        query += " ORDER BY v.fecha DESC"
        
        cursor.execute(query, params)
        ventas = cursor.fetchall()
        
        efectivo = 0.0
        transferencia = 0.0
        
        for v in ventas:
            if v['metodo_pago'] == 'EFECTIVO':
                efectivo += v['total']
            elif v['metodo_pago'] in ('TRANSFERENCIA', 'TARJETA/TRANSFERENCIA'):
                transferencia += v['total']
            elif v['metodo_pago'] == 'MIXTO':
                cursor.execute("""
                    SELECT monto, metodo_pago 
                    FROM caja_movimientos 
                    WHERE descripcion LIKE ? AND tipo = 'VENTA'
                """, (f"Venta #{v['id']} (Mixto)%",))
                movs = cursor.fetchall()
                for m in movs:
                    if m['metodo_pago'] == 'EFECTIVO':
                        efectivo += m['monto']
                    elif m['metodo_pago'] in ('TRANSFERENCIA', 'TARJETA/TRANSFERENCIA'):
                        transferencia += m['monto']
        
        conn.close()
        return {
            'ventas': ventas,
            'total_efectivo': efectivo,
            'total_transferencia': transferencia,
            'total_general': sum(v['total'] for v in ventas)
        }

    @staticmethod
    def get_productos_mas_vendidos(fecha_desde: str, fecha_hasta: str):
        desde = f"{fecha_desde} 00:00:00"
        hasta = f"{fecha_hasta} 23:59:59"
        
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT p.codigo_barras, p.nombre, sum(vd.cantidad) as cant_total, sum(vd.subtotal) as recaudacion
            FROM ventas_detalle vd
            JOIN ventas v ON vd.venta_id = v.id
            JOIN productos p ON vd.producto_id = p.id
            WHERE v.estado != 'CANCELADA' AND datetime(v.fecha, 'localtime') BETWEEN ? AND ?
            GROUP BY p.id
            ORDER BY cant_total DESC
        """, (desde, hasta))
        
        productos = cursor.fetchall()
        conn.close()
        return productos

    @staticmethod
    def get_cierres_caja(fecha_desde: str, fecha_hasta: str):
        desde = f"{fecha_desde} 00:00:00"
        hasta = f"{fecha_hasta} 23:59:59"
        
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, monto_inicial, fecha_apertura, fecha_cierre, monto_cierre, estado
            FROM caja_sesiones
            WHERE datetime(fecha_apertura, 'localtime') BETWEEN ? AND ?
            ORDER BY fecha_apertura DESC
        """, (desde, hasta))
        
        cierres = cursor.fetchall()
        conn.close()
        return cierres

    @staticmethod
    def get_alertas_reposicion():
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT codigo_barras, nombre, stock_actual, stock_minimo, stock_maximo,
                   (stock_maximo - stock_actual) as sugerido_pedir
            FROM productos
            WHERE stock_actual <= stock_minimo
            ORDER BY sugerido_pedir DESC
        """)
        
        alertas = cursor.fetchall()
        conn.close()
        return alertas

    @staticmethod
    def get_reporte_ganancias(fecha_desde: str, fecha_hasta: str):
        desde = f"{fecha_desde} 00:00:00"
        hasta = f"{fecha_hasta} 23:59:59"
        
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                DATE(datetime(v.fecha, 'localtime')) as dia,
                SUM(vd.subtotal) as total_vendido,
                SUM(vd.costo_unitario * vd.cantidad) as costo_total,
                (SUM(vd.subtotal) - SUM(vd.costo_unitario * vd.cantidad)) as ganancia_neta
            FROM ventas_detalle vd
            JOIN ventas v ON vd.venta_id = v.id
            WHERE v.estado != 'CANCELADA' AND datetime(v.fecha, 'localtime') BETWEEN ? AND ?
            GROUP BY dia
            ORDER BY dia DESC
        """, (desde, hasta))
        
        ganancias = cursor.fetchall()
        
        cursor.execute("""
            SELECT 
                SUM(vd.subtotal) as total_vendido,
                SUM(vd.costo_unitario * vd.cantidad) as costo_total,
                (SUM(vd.subtotal) - SUM(vd.costo_unitario * vd.cantidad)) as ganancia_neta
            FROM ventas_detalle vd
            JOIN ventas v ON vd.venta_id = v.id
            WHERE v.estado != 'CANCELADA' AND datetime(v.fecha, 'localtime') BETWEEN ? AND ?
        """, (desde, hasta))
        totales = cursor.fetchone()
        
        conn.close()
        
        return {
            'ganancias_por_dia': ganancias,
            'totales': {
                'total_vendido': totales['total_vendido'] or 0.0,
                'costo_total': totales['costo_total'] or 0.0,
                'ganancia_neta': totales['ganancia_neta'] or 0.0
            }
        }

    @staticmethod
    def get_ventas_por_rubro(fecha_desde: str, fecha_hasta: str):
        desde = f"{fecha_desde} 00:00:00"
        hasta = f"{fecha_hasta} 23:59:59"
        
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COALESCE(c.nombre, 'Sin Rubro') as rubro,
                SUM(vd.subtotal) as total_vendido,
                SUM(vd.costo_unitario * vd.cantidad) as costo_total,
                (SUM(vd.subtotal) - SUM(vd.costo_unitario * vd.cantidad)) as ganancia_neta
            FROM ventas_detalle vd
            JOIN ventas v ON vd.venta_id = v.id
            JOIN productos p ON vd.producto_id = p.id
            LEFT JOIN categorias c ON p.categoria_id = c.id
            WHERE v.estado != 'CANCELADA' AND datetime(v.fecha, 'localtime') BETWEEN ? AND ?
            GROUP BY c.id, c.nombre
            ORDER BY total_vendido DESC
        """, (desde, hasta))
        
        rubros = cursor.fetchall()
        conn.close()
        
        return rubros



