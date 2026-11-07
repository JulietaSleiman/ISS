"""Sincronización acotada de instantáneas, cierres y comandos, fuera de la UI."""
from contextlib import closing
import json
import threading
from urllib.parse import urlencode

from src.db.database import get_connection
from src.core.auth_manager import AuthManager
from src.core import supabase_client


class SyncManager:
    _lock = threading.Lock()
    ENTITY_BATCH = 50
    CLOSE_BATCH = 20
    COMMAND_BATCH = 50

    @staticmethod
    def _exists(conn, table):
        return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None

    @staticmethod
    def pending_count():
        user = AuthManager.current_user()
        if user is None:
            return 0
        with closing(get_connection()) as conn:
            total = conn.execute("SELECT COUNT(*) AS n FROM sync_cierres WHERE estado='PENDIENTE' AND sucursal_id=?", (user.branch_id,)).fetchone()['n']
            if SyncManager._exists(conn, 'sync_entidades'):
                total += conn.execute("SELECT COUNT(*) AS n FROM sync_entidades WHERE estado='PENDIENTE' AND sucursal_id=?", (user.branch_id,)).fetchone()['n']
                from src.core.entity_sync_store import EntitySyncStore
                total += EntitySyncStore.initial_pending_count(user)
            if SyncManager._exists(conn, 'sync_comandos_aplicados'):
                total += conn.execute('SELECT COUNT(*) AS n FROM sync_comandos_aplicados WHERE ack_en IS NULL').fetchone()['n']
            return total

    count_pending = pending_count

    @staticmethod
    def _error(result, exc):
        message = str(exc)
        if message not in result['errors']:
            result['errors'].append(message)
        result['error'] = '; '.join(result['errors'])

    @staticmethod
    def _ack_ids(response, expected):
        acknowledged = response.get('acknowledged') if isinstance(response, dict) else None
        if not isinstance(acknowledged, list) or any(not isinstance(item, str) for item in acknowledged):
            raise ValueError('El servidor no confirmó los identificadores enviados.')
        if len(set(acknowledged)) != len(acknowledged) or not set(acknowledged).issubset(expected):
            raise ValueError('El servidor confirmó identificadores inesperados; se conservan los pendientes.')
        return set(acknowledged)

    @staticmethod
    def _pull_commands(user, token, result):
        from src.core.entity_sync_store import EntitySyncStore
        query = urlencode({'sucursal_id': f'eq.{user.branch_id}', 'estado': 'eq.PENDIENTE',
                           'order': 'created_at.asc,id.asc', 'limit': SyncManager.COMMAND_BATCH})
        commands = supabase_client.request('GET', '/rest/v1/comandos_precios?' + query, access_token=token)
        if not isinstance(commands, list) or len(commands) > SyncManager.COMMAND_BATCH:
            raise ValueError('La lista de comandos de precios no es válida.')
        for command in commands:
            if not isinstance(command, dict) or command.get('sucursal_id') != user.branch_id:
                raise ValueError('Se recibió un comando de otra sucursal.')
            EntitySyncStore.apply_price_command(command, user)

    @staticmethod
    def _upload_entities(user, token, result):
        with closing(get_connection()) as conn:
            actor_filter = '' if user.role == 'admin' else ' AND usuario_id=?'
            args = (user.branch_id,) if user.role == 'admin' else (user.branch_id, user.user_id)
            events = conn.execute("SELECT * FROM sync_entidades WHERE estado='PENDIENTE' AND sucursal_id=?" + actor_filter + ' ORDER BY creado_en,id LIMIT ?', (*args, SyncManager.ENTITY_BATCH)).fetchall()
        envelopes = [{'id': row['id'], 'tipo': row['tipo'], 'entidad_id': row['entidad_id'],
                      'revision': row['revision'], 'usuario_id': row['usuario_id'],
                      'payload': json.loads(row['payload'])} for row in events]
        expected = {event['id'] for event in envelopes}
        pending_after = max(0, SyncManager.pending_count() - len(events))
        try:
            response = supabase_client.request('POST', '/rest/v1/rpc/sincronizar_entidades',
                {'p_eventos': envelopes, 'p_pendientes': pending_after}, access_token=token)
            acknowledged = SyncManager._ack_ids(response, expected)
        except Exception as exc:
            SyncManager._record_entity_attempt(events, (), str(exc))
            raise
        SyncManager._record_entity_attempt(events, acknowledged, None)
        result['sent'] += len(acknowledged)
        if acknowledged != expected:
            raise ValueError('Faltan confirmaciones del servidor; se reintentarán las operaciones pendientes.')

    @staticmethod
    def _record_entity_attempt(events, acknowledged, error):
        with closing(get_connection()) as conn:
            with conn:
                for row in events:
                    if row['id'] in acknowledged:
                        conn.execute("UPDATE sync_entidades SET estado='ENVIADO',intentos=intentos+1,ultimo_error=NULL,enviado_en=CURRENT_TIMESTAMP WHERE id=? AND estado='PENDIENTE'", (row['id'],))
                    else:
                        conn.execute("UPDATE sync_entidades SET intentos=intentos+1,ultimo_error=? WHERE id=? AND estado='PENDIENTE'", (error or 'Falta confirmación del servidor', row['id']))

    @staticmethod
    def _ack_commands(user, token, result):
        with closing(get_connection()) as conn:
            rows = conn.execute('SELECT id,resultado FROM sync_comandos_aplicados WHERE ack_en IS NULL ORDER BY id LIMIT ?', (SyncManager.COMMAND_BATCH,)).fetchall()
        if not rows:
            return
        results = [json.loads(row['resultado']) for row in rows]
        expected = {row['id'] for row in rows}
        response = supabase_client.request('POST', '/rest/v1/rpc/confirmar_comandos_precios', {'p_resultados': results}, access_token=token)
        acknowledged = SyncManager._ack_ids(response, expected)
        with closing(get_connection()) as conn:
            with conn:
                for command_id in acknowledged:
                    conn.execute('UPDATE sync_comandos_aplicados SET ack_en=CURRENT_TIMESTAMP WHERE id=? AND ack_en IS NULL', (command_id,))
        result['sent'] += len(acknowledged)
        if acknowledged != expected:
            raise ValueError('Faltan confirmaciones de comandos de precios; se reintentará su recepción.')

    @staticmethod
    def _upload_closes(user, token, result):
        # Se conserva el autor original; un administrador no suplanta al actor.
        with closing(get_connection()) as conn:
            closes = conn.execute("SELECT id,payload FROM sync_cierres WHERE estado='PENDIENTE' AND sucursal_id=? AND usuario_id=? ORDER BY creado_en,id LIMIT ?", (user.branch_id,user.user_id,SyncManager.CLOSE_BATCH)).fetchall()
        for close in closes:
            try:
                supabase_client.request('POST', '/rest/v1/cierres_caja?on_conflict=id', payload=json.loads(close['payload']), access_token=token,
                    headers={'Prefer': 'resolution=ignore-duplicates,return=minimal'})
            except Exception as exc:
                with closing(get_connection()) as conn:
                    with conn:
                        conn.execute("UPDATE sync_cierres SET intentos=intentos+1,ultimo_error=? WHERE id=? AND estado='PENDIENTE'", (str(exc),close['id']))
                raise
            with closing(get_connection()) as conn:
                with conn:
                    conn.execute("UPDATE sync_cierres SET estado='ENVIADO',intentos=intentos+1,ultimo_error=NULL,enviado_en=CURRENT_TIMESTAMP WHERE id=? AND estado='PENDIENTE'", (close['id'],))
            result['sent'] += 1

    @staticmethod
    def _has_more_own(user):
        from src.core.entity_sync_store import EntitySyncStore
        if EntitySyncStore.initial_pending_count(user):
            return True
        with closing(get_connection()) as conn:
            if conn.execute("SELECT 1 FROM sync_cierres WHERE estado='PENDIENTE' AND sucursal_id=? AND usuario_id=? LIMIT 1", (user.branch_id,user.user_id)).fetchone():
                return True
            if SyncManager._exists(conn,'sync_entidades'):
                actor_filter = '' if user.role == 'admin' else ' AND usuario_id=?'
                args = (user.branch_id,) if user.role == 'admin' else (user.branch_id,user.user_id)
                if conn.execute("SELECT 1 FROM sync_entidades WHERE estado='PENDIENTE' AND sucursal_id=?" + actor_filter + ' LIMIT 1',args).fetchone():
                    return True
            return bool(conn.execute('SELECT 1 FROM sync_comandos_aplicados WHERE ack_en IS NULL LIMIT 1').fetchone())

    @staticmethod
    def sync_pending():
        result = {'sent': 0, 'pending': 0, 'error': None, 'errors': [], 'has_more_own': False}
        if not SyncManager._lock.acquire(blocking=False):
            result['pending'] = SyncManager.pending_count()
            return result
        try:
            from src.core.entity_sync_store import EntitySyncStore
            user = AuthManager.require_user()
            EntitySyncStore.validate_installation(user)  # Sucursal equivocada: detener todo.
            try:
                EntitySyncStore.prepare_initial_sync(user)
            except Exception as exc:
                # Un registro antiguo inválido no impide enviar cierres ya válidos.
                SyncManager._error(result,exc)
            token = AuthManager.ensure_auth_token()
            # Fallar en una etapa nueva no suprime los cierres si falta aplicar 004.
            for stage in (SyncManager._pull_commands, SyncManager._upload_entities,
                          SyncManager._ack_commands, SyncManager._upload_closes):
                try:
                    stage(user,token,result)
                except Exception as exc:
                    SyncManager._error(result,exc)
            result['has_more_own'] = SyncManager._has_more_own(user)
        except Exception as exc:
            SyncManager._error(result,exc)
        finally:
            try:
                result['pending'] = SyncManager.pending_count()
            except Exception as exc:
                SyncManager._error(result,exc)
            finally:
                SyncManager._lock.release()
        return result
