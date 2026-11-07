from contextlib import closing
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sqlite3
import uuid

from src.db import database
from src.db.database import get_connection
from src.core.auth_manager import AuthManager


class CajaAnteriorError(ValueError):
    """Un turno sin identidad histórica requiere un cierre explícito de transición."""


class CajaManager:
    @staticmethod
    def _check_binding(conn, user):
        binding = conn.execute("SELECT value FROM sync_configuracion WHERE key = 'sucursal_id'").fetchone()
        if binding and binding['value'] != user.branch_id:
            raise ValueError('La base local ya está vinculada a otra sucursal. Revise la instalación antes de operar.')
        foreign = conn.execute('SELECT 1 FROM caja_sesiones WHERE sucursal_id IS NOT NULL AND sucursal_id <> ? LIMIT 1', (user.branch_id,)).fetchone()
        if foreign:
            raise ValueError('La base local contiene turnos de otra sucursal. Revise la instalación antes de operar.')

    @staticmethod
    def _monto(value):
        try:
            monto = float(value)
        except (ValueError, TypeError):
            raise ValueError("Ingrese un importe válido.") from None
        if not math.isfinite(monto) or monto < 0:
            raise ValueError("El importe debe ser finito y mayor o igual a cero.")
        return round(monto, 2)

    @staticmethod
    def _activa(conn, user):
        CajaManager._check_binding(conn, user)
        sesiones = conn.execute("SELECT * FROM caja_sesiones WHERE estado = 'ABIERTA' ORDER BY id DESC").fetchall()
        for sesion in sesiones:
            if all(sesion[key] is None for key in ('responsable_id', 'sucursal_id', 'sync_id')):
                raise CajaAnteriorError("Hay una caja anterior al inicio de sesión sin responsable. Use 'Cerrar caja anterior' en Caja Diaria para contar el efectivo y registrar su cierre de transición con respaldo; la apertura histórica conservará su responsable sin registrar.")
            if not all(sesion[key] for key in ('responsable_id', 'sucursal_id', 'sync_id')):
                raise ValueError("La caja abierta tiene datos de identidad incompletos. Contacte al administrador; no puede tratarse como una caja anterior ni reasignarse automáticamente.")
            if sesion['sucursal_id'] != user.branch_id:
                raise ValueError("La base local tiene una caja abierta de otra sucursal. Revise la instalación antes de operar.")
            if sesion['responsable_id'] != user.user_id and user.role != 'admin':
                raise ValueError("El turno abierto pertenece a otro responsable. Debe cerrarlo su responsable o un administrador antes de cambiar de operador.")
        return sesiones[0] if sesiones else None

    @staticmethod
    def obtener_sesion_activa():
        user = AuthManager.require_user()
        with closing(get_connection()) as conn:
            return CajaManager._activa(conn, user)

    @staticmethod
    def obtener_cajas_anteriores():
        """Turnos completamente anteriores a la identidad por usuario, sin reasignarlos."""
        user = AuthManager.require_user()
        with closing(get_connection()) as conn:
            CajaManager._check_binding(conn, user)
            return [dict(row) for row in conn.execute("""
                SELECT * FROM caja_sesiones
                WHERE estado = 'ABIERTA' AND responsable_id IS NULL
                  AND sucursal_id IS NULL AND sync_id IS NULL
                ORDER BY id
            """).fetchall()]

    @staticmethod
    def _respaldar_transicion(caja_id):
        """Copia SQLite consistente desde otra conexión, antes de modificar el turno."""
        backup_dir = Path(database.DB_PATH).parent / 'Backups_Transicion'
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        backup_path = backup_dir / f'caja_{caja_id}_{stamp}_{uuid.uuid4().hex}.sqlite'
        # Reservar el nombre en modo exclusivo: no se sobrescribe ningún respaldo.
        with backup_path.open('xb'):
            pass
        try:
            # La conexión que posee BEGIN IMMEDIATE no se usa como fuente: el
            # backup de su propia transacción de escritura puede quedar esperando.
            with closing(get_connection()) as source:
                with closing(sqlite3.connect(backup_path)) as destination:
                    source.backup(destination)
        except Exception:
            try:
                backup_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise
        return str(backup_path.resolve())

    @staticmethod
    def cerrar_caja_anterior(caja_id, monto_contado, motivo):
        """Cierre explícito auditado; mantiene desconocida la identidad de apertura."""
        user = AuthManager.require_user()
        contado = CajaManager._monto(monto_contado)
        if not isinstance(motivo, str) or len(motivo.strip()) < 10:
            raise ValueError("Explique el motivo del cierre de transición con al menos 10 caracteres.")
        motivo = motivo.strip()
        with closing(get_connection()) as conn:
            with conn:
                conn.execute('BEGIN IMMEDIATE')
                CajaManager._check_binding(conn, user)
                sesion = conn.execute("""
                    SELECT * FROM caja_sesiones WHERE id = ? AND estado = 'ABIERTA'
                      AND responsable_id IS NULL AND sucursal_id IS NULL AND sync_id IS NULL
                """, (caja_id,)).fetchone()
                if not sesion:
                    raise ValueError("La caja seleccionada no es una caja anterior abierta sin responsable, o ya fue cerrada.")
                # El respaldo se genera bajo el bloqueo de escritura, pero usando
                # un lector aparte para incluir todas las operaciones confirmadas.
                # Un fallo aquí aborta el cierre sin atribuir ni modificar datos.
                backup_path = CajaManager._respaldar_transicion(sesion['id'])
                resumen = CajaManager.obtener_resumen(sesion['id'], _connection=conn)
                esperado = round(resumen['total_efectivo_esperado'], 2)
                diferencia = round(contado - esperado, 2)
                conn.execute("""
                    UPDATE caja_sesiones SET estado = 'CERRADA', fecha_cierre = CURRENT_TIMESTAMP,
                        monto_cierre = ?, monto_esperado = ?, diferencia = ?,
                        cierre_usuario_id = ?, cierre_usuario_nombre = ? WHERE id = ?
                """, (contado, esperado, diferencia, user.user_id, user.username, sesion['id']))
                conn.execute("""
                    INSERT INTO caja_regularizaciones
                        (caja_id, usuario_id, nombre, sucursal_id, motivo, backup_path)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (sesion['id'], user.user_id, user.username, user.branch_id, motivo, backup_path))
                # No crea sync_id ni evento cloud: la apertura no tiene responsable
                # identificado y no cumple el contrato de los nuevos cierres.
                return {'caja_id': sesion['id'], 'esperado': esperado, 'contado': contado,
                        'diferencia': diferencia, 'backup_path': backup_path}

    @staticmethod
    def abrir_caja(monto_inicial: float):
        user = AuthManager.require_user()
        monto = CajaManager._monto(monto_inicial)
        with closing(get_connection()) as conn:
            with conn:
                conn.execute("BEGIN IMMEDIATE")
                if CajaManager._activa(conn, user):
                    raise ValueError("Ya existe una caja abierta.")
                cursor = conn.execute("""
                    INSERT INTO caja_sesiones
                    (monto_inicial, estado, sync_id, sucursal_id, responsable_id, responsable_nombre)
                    VALUES (?, 'ABIERTA', ?, ?, ?, ?)
                """, (monto, str(uuid.uuid4()), user.branch_id, user.user_id, user.username))
                return cursor.lastrowid

    @staticmethod
    def cerrar_caja(monto_cierre: float):
        user = AuthManager.require_user()
        monto = CajaManager._monto(monto_cierre)
        with closing(get_connection()) as conn:
            with conn:
                conn.execute("BEGIN IMMEDIATE")
                sesion = CajaManager._activa(conn, user)
                if not sesion:
                    raise ValueError("No hay ninguna caja abierta para cerrar.")
                if sesion['responsable_id'] != user.user_id and user.role != 'admin':
                    raise ValueError("Solo el responsable del turno o un administrador puede cerrar esta caja.")
                resumen = CajaManager.obtener_resumen(sesion['id'], _connection=conn)
                esperado = round(resumen['total_efectivo_esperado'], 2)
                diferencia = round(monto - esperado, 2)
                conn.execute("""
                    UPDATE caja_sesiones SET estado = 'CERRADA', fecha_cierre = CURRENT_TIMESTAMP,
                        monto_cierre = ?, monto_esperado = ?, diferencia = ?,
                        cierre_usuario_id = ?, cierre_usuario_nombre = ? WHERE id = ? AND estado = 'ABIERTA'
                """, (monto, esperado, diferencia, user.user_id, user.username, sesion['id']))
                # Alias sin 'fecha' evita que el row factory convierta UTC a hora local.
                tiempos = conn.execute("""
                    SELECT strftime('%Y-%m-%dT%H:%M:%SZ', fecha_apertura) AS opened_at,
                           strftime('%Y-%m-%dT%H:%M:%SZ', fecha_cierre) AS closed_at
                    FROM caja_sesiones WHERE id = ?
                """, (sesion['id'],)).fetchone()
                payload = {
                    'id': sesion['sync_id'], 'sucursal_id': user.branch_id,
                    'responsable_id': sesion['responsable_id'],
                    'responsable_nombre': sesion['responsable_nombre'],
                    'cierre_usuario_id': user.user_id, 'cierre_usuario_nombre': user.username,
                    'fecha_apertura': tiempos['opened_at'], 'fecha_cierre': tiempos['closed_at'],
                    'monto_inicial': sesion['monto_inicial'], 'monto_esperado': esperado,
                    'monto_cierre': monto, 'diferencia': diferencia, 'resumen': resumen,
                }
                conn.execute("""
                    INSERT INTO sync_cierres (id, caja_sesion_id, sucursal_id, usuario_id, payload)
                    VALUES (?, ?, ?, ?, ?)
                """, (sesion['sync_id'], sesion['id'], user.branch_id, user.user_id,
                      json.dumps(payload, ensure_ascii=False, allow_nan=False)))
                return {'id': sesion['id'], 'sync_id': sesion['sync_id'],
                        'monto_esperado': esperado, 'monto_cierre': monto, 'diferencia': diferencia}

    @staticmethod
    def registrar_movimiento(caja_sesion_id: int, tipo: str, monto: float, metodo_pago: str, descripcion: str = ""):
        user = AuthManager.require_user()
        monto = CajaManager._monto(monto)
        if tipo not in ('INGRESO', 'EGRESO'):
            raise ValueError("El movimiento manual debe ser INGRESO o EGRESO.")
        with closing(get_connection()) as conn:
            with conn:
                conn.execute("BEGIN IMMEDIATE")
                sesion = CajaManager._activa(conn, user)
                if not sesion or sesion['id'] != caja_sesion_id:
                    raise ValueError("La caja ya no está abierta.")
                if sesion['responsable_id'] != user.user_id and user.role != 'admin':
                    raise ValueError("El movimiento debe registrarlo el responsable del turno.")
                conn.execute("""
                    INSERT INTO caja_movimientos (caja_sesion_id, tipo, monto, metodo_pago, descripcion)
                    VALUES (?, ?, ?, ?, ?)
                """, (caja_sesion_id, tipo, monto, metodo_pago, descripcion))

    @staticmethod
    def obtener_resumen(caja_sesion_id: int, _connection=None):
        conn = _connection or get_connection()
        cursor = conn.cursor()
        
        resumen = {
            'monto_inicial': 0.0,
            'ventas_efectivo': 0.0,
            'ventas_transferencia': 0.0,
            'ventas_fiadas': 0.0,
            'ventas_otros': 0.0,
            'ingresos_manuales': 0.0,
            'egresos_manuales': 0.0,
            'pagos_proveedor_efectivo': 0.0,
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
            elif m['tipo'] == 'PAGO_PROVEEDOR' and m['metodo_pago'] == 'EFECTIVO':
                # Los pagos a proveedores se guardan con signo negativo.
                resumen['pagos_proveedor_efectivo'] -= m['suma']
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
            resumen['egresos_manuales'] -
            resumen['pagos_proveedor_efectivo']
        )
        
        if _connection is None:
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
