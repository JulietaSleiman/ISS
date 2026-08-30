from src.db.database import get_connection

class CtaCteProveedoresManager:
    @staticmethod
    def get_saldo(proveedor_id):
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT sum(monto) as total_deuda FROM cta_cte_proveedores_movimientos WHERE proveedor_id = ? AND tipo = 'DEUDA'", (proveedor_id,))
        deuda = cursor.fetchone()['total_deuda'] or 0.0
        
        cursor.execute("SELECT sum(monto) as total_pagos FROM cta_cte_proveedores_movimientos WHERE proveedor_id = ? AND tipo = 'PAGO'", (proveedor_id,))
        pagos = cursor.fetchone()['total_pagos'] or 0.0
        
        conn.close()
        return deuda - pagos

    @staticmethod
    def get_historial(proveedor_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM cta_cte_proveedores_movimientos WHERE proveedor_id = ? ORDER BY fecha DESC", (proveedor_id,))
        historial = cursor.fetchall()
        conn.close()
        return [dict(h) for h in historial]

    @staticmethod
    def registrar_pago(proveedor_id, monto, caja_sesion_id, detalle="Abono a proveedor", metodo_pago="EFECTIVO"):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            # 1. Insertar movimiento en cta cte proveedores
            cursor.execute("""
            INSERT INTO cta_cte_proveedores_movimientos (proveedor_id, caja_sesion_id, tipo, monto, detalle)
            VALUES (?, ?, 'PAGO', ?, ?)
            """, (proveedor_id, caja_sesion_id, monto, detalle))
            
            # 2. Insertar movimiento de caja (Egreso de dinero)
            cursor.execute("""
            INSERT INTO caja_movimientos (caja_sesion_id, tipo, monto, metodo_pago, descripcion)
            VALUES (?, 'PAGO_PROVEEDOR', ?, ?, ?)
            """, (caja_sesion_id, -monto, metodo_pago, f"Pago a Proveedor - {detalle}"))
            
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def registrar_deuda(proveedor_id, monto, caja_sesion_id=None, detalle="Compra de mercadería"):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            # Insertar movimiento de DEUDA en cta cte proveedores
            cursor.execute("""
            INSERT INTO cta_cte_proveedores_movimientos (proveedor_id, caja_sesion_id, tipo, monto, detalle)
            VALUES (?, ?, 'DEUDA', ?, ?)
            """, (proveedor_id, caja_sesion_id, monto, detalle))
            
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
