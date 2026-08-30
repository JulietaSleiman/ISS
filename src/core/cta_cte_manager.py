from src.db.database import get_connection

class CtaCteManager:
    @staticmethod
    def get_saldo(cliente_id):
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT sum(monto) as total_deuda FROM cta_cte_movimientos WHERE cliente_id = ? AND tipo = 'DEUDA'", (cliente_id,))
        deuda = cursor.fetchone()['total_deuda'] or 0.0
        
        cursor.execute("SELECT sum(monto) as total_pagos FROM cta_cte_movimientos WHERE cliente_id = ? AND tipo = 'PAGO'", (cliente_id,))
        pagos = cursor.fetchone()['total_pagos'] or 0.0
        
        conn.close()
        return deuda - pagos

    @staticmethod
    def get_historial(cliente_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM cta_cte_movimientos WHERE cliente_id = ? ORDER BY fecha DESC", (cliente_id,))
        historial = cursor.fetchall()
        conn.close()
        return [dict(h) for h in historial]

    @staticmethod
    def registrar_pago(cliente_id, monto, caja_sesion_id, detalle="Abono a cuenta", metodo_pago="EFECTIVO"):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            # 1. Insertar movimiento en cta cte
            cursor.execute("""
            INSERT INTO cta_cte_movimientos (cliente_id, caja_sesion_id, tipo, monto, detalle)
            VALUES (?, ?, 'PAGO', ?, ?)
            """, (cliente_id, caja_sesion_id, monto, detalle))
            
            # 2. Insertar movimiento de caja SOLO si no es canje de mercadería
            if metodo_pago != 'CANJE / MERCADERIA':
                cursor.execute("""
                INSERT INTO caja_movimientos (caja_sesion_id, tipo, monto, metodo_pago, descripcion)
                VALUES (?, 'PAGO_CTA_CTE', ?, ?, ?)
                """, (caja_sesion_id, monto, metodo_pago, f"Pago Cta Cte - {detalle}"))
            
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
