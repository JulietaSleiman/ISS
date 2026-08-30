from src.db.database import get_connection
from datetime import datetime

class CajaManager:
    @staticmethod
    def obtener_sesion_activa():
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM caja_sesiones WHERE estado = 'ABIERTA' ORDER BY id DESC LIMIT 1")
        sesion = cursor.fetchone()
        conn.close()
        return sesion

    @staticmethod
    def abrir_caja(monto_inicial: float):
        sesion_activa = CajaManager.obtener_sesion_activa()
        if sesion_activa:
            raise Exception("Ya existe una caja abierta.")
        
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
            INSERT INTO caja_sesiones (monto_inicial, estado)
            VALUES (?, 'ABIERTA')
            """, (monto_inicial,))
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def cerrar_caja(monto_cierre: float):
        sesion_activa = CajaManager.obtener_sesion_activa()
        if not sesion_activa:
            raise Exception("No hay ninguna caja abierta para cerrar.")
        
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
            UPDATE caja_sesiones 
            SET estado = 'CERRADA', fecha_cierre = CURRENT_TIMESTAMP, monto_cierre = ?
            WHERE id = ?
            """, (monto_cierre, sesion_activa['id']))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def registrar_movimiento(caja_sesion_id: int, tipo: str, monto: float, metodo_pago: str, descripcion: str = ""):
        """Registra un ingreso o egreso en la caja (ej: pago a proveedor, retiro de efectivo)."""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
            INSERT INTO caja_movimientos (caja_sesion_id, tipo, monto, metodo_pago, descripcion)
            VALUES (?, ?, ?, ?, ?)
            """, (caja_sesion_id, tipo, monto, metodo_pago, descripcion))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def obtener_resumen(caja_sesion_id: int):
        conn = get_connection()
        cursor = conn.cursor()
        
        resumen = {
            'monto_inicial': 0.0,
            'ventas_efectivo': 0.0,
            'ventas_transferencia': 0.0,
            'ventas_fiadas': 0.0,
            'ventas_otros': 0.0,
            'ingresos_manuales': 0.0,
            'egresos_manuales': 0.0,
            'pagos_deuda_efectivo': 0.0,
            'pagos_deuda_transferencia': 0.0,
            'total_efectivo_esperado': 0.0,
            'total_vendido': 0.0
        }
        
        # 1. Obtener monto inicial
        cursor.execute("SELECT monto_inicial FROM caja_sesiones WHERE id = ?", (caja_sesion_id,))
        sesion = cursor.fetchone()
        if sesion:
            resumen['monto_inicial'] = sesion['monto_inicial']
            
        # 2. Obtener ventas
        cursor.execute("SELECT id, metodo_pago, total FROM ventas WHERE caja_sesion_id = ? AND estado != 'CANCELADA'", (caja_sesion_id,))
        ventas = cursor.fetchall()
        for v in ventas:
            if v['metodo_pago'] == 'EFECTIVO':
                resumen['ventas_efectivo'] += v['total']
            elif v['metodo_pago'] in ['TRANSFERENCIA', 'TARJETA/TRANSFERENCIA']:
                resumen['ventas_transferencia'] += v['total']
            elif v['metodo_pago'] == 'FIADO / CTA. CTE.':
                resumen['ventas_fiadas'] += v['total']
            elif v['metodo_pago'] == 'MIXTO':
                # Buscar el desglose en la tabla caja_movimientos para esta venta mixta
                desc = f"Venta #{v['id']} (Mixto)"
                cursor.execute("SELECT metodo_pago, SUM(monto) as monto FROM caja_movimientos WHERE caja_sesion_id = ? AND descripcion = ? GROUP BY metodo_pago", (caja_sesion_id, desc))
                movs = cursor.fetchall()
                if movs:
                    for m in movs:
                        if m['metodo_pago'] == 'EFECTIVO':
                            resumen['ventas_efectivo'] += m['monto']
                        elif m['metodo_pago'] in ['TRANSFERENCIA', 'TARJETA/TRANSFERENCIA']:
                            resumen['ventas_transferencia'] += m['monto']
                        else:
                            resumen['ventas_otros'] += m['monto']
                else:
                    # Fallback si por alguna razón no se encontró el movimiento
                    resumen['ventas_otros'] += v['total']
            else:
                resumen['ventas_otros'] += v['total']
                
        resumen['total_vendido'] = resumen['ventas_efectivo'] + resumen['ventas_transferencia'] + resumen['ventas_fiadas'] + resumen['ventas_otros']
                
        # 3. Obtener movimientos manuales
        cursor.execute("SELECT tipo, metodo_pago, SUM(monto) as suma FROM caja_movimientos WHERE caja_sesion_id = ? GROUP BY tipo, metodo_pago", (caja_sesion_id,))
        movimientos = cursor.fetchall()
        for m in movimientos:
            if m['tipo'] == 'INGRESO' and m['metodo_pago'] == 'EFECTIVO':
                resumen['ingresos_manuales'] += m['suma']
            elif m['tipo'] == 'EGRESO' and m['metodo_pago'] == 'EFECTIVO':
                resumen['egresos_manuales'] += m['suma']
            elif m['tipo'] == 'PAGO_CTA_CTE':
                if m['metodo_pago'] == 'EFECTIVO':
                    resumen['pagos_deuda_efectivo'] += m['suma']
                elif m['metodo_pago'] in ['TRANSFERENCIA', 'TARJETA/TRANSFERENCIA']:
                    resumen['pagos_deuda_transferencia'] += m['suma']
                
        # 4. Calcular total efectivo esperado
        resumen['total_efectivo_esperado'] = (
            resumen['monto_inicial'] + 
            resumen['ventas_efectivo'] + 
            resumen['ingresos_manuales'] +
            resumen['pagos_deuda_efectivo'] - 
            resumen['egresos_manuales']
        )
        
        conn.close()
        return resumen

    @staticmethod
    def obtener_movimientos(caja_sesion_id: int):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM caja_movimientos WHERE caja_sesion_id = ? ORDER BY fecha DESC", (caja_sesion_id,))
        movs = cursor.fetchall()
        conn.close()
        return [dict(m) for m in movs]
