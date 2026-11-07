from contextlib import closing
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from src.db import database
from src.core.auth_manager import AuthManager
from src.core.caja_manager import CajaManager
from src.core.sync_manager import SyncManager
from src.core.ventas_manager import VentasManager
from src.core.supabase_client import NetworkError


class CashIdentitySyncTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(temp.cleanup)
        self.user = SimpleNamespace(
            user_id='11111111-1111-4111-8111-111111111111', username='caja1',
            branch_id='f2985c88-2a4e-4e73-92d5-85d905b3db41',
            branch_name='Estación de Simoca', role='cajero')
        for target, value in (
            ('src.db.database.DB_PATH', Path(temp.name) / 'test.sqlite'),
            ('src.db.database.auto_backup_db', lambda: None),
        ):
            p = patch(target, value)
            p.start()
            self.addCleanup(p.stop)
        self.require = patch.object(AuthManager, 'require_user', side_effect=lambda: self.user).start()
        self.addCleanup(patch.stopall)
        patch.object(AuthManager, 'current_user', side_effect=lambda: self.user).start()
        self.token = patch.object(AuthManager, 'ensure_auth_token', return_value='test-token').start()
        self.remote = patch('src.core.sync_manager.supabase_client.request').start()
        database.init_db()

    def sql(self, sql, params=()):
        with closing(database.get_connection()) as conn:
            with conn:
                return [dict(row) for row in conn.execute(sql, params).fetchall()]

    def test_cash_close_records_identity_counted_amount_and_utc_snapshot_offline(self):
        caja = CajaManager.abrir_caja(100)
        CajaManager.registrar_movimiento(caja, 'INGRESO', 50, 'EFECTIVO', 'Fondo')
        result = CajaManager.cerrar_caja(90)
        self.assertEqual((result['monto_esperado'], result['monto_cierre'], result['diferencia']), (150, 90, -60))
        row = self.sql('SELECT * FROM caja_sesiones')[0]
        self.assertEqual(row['responsable_id'], self.user.user_id)
        self.assertEqual(row['cierre_usuario_id'], self.user.user_id)
        self.assertEqual(row['sucursal_id'], self.user.branch_id)
        outbox = self.sql('SELECT * FROM sync_cierres')[0]
        data = json.loads(outbox['payload'])
        self.assertEqual(data['id'], row['sync_id'])
        self.assertTrue(data['fecha_apertura'].endswith('Z'))
        self.assertTrue(data['fecha_cierre'].endswith('Z'))
        self.assertEqual(data['resumen']['ingresos_manuales'], 50)
        self.assertEqual(outbox['estado'], 'PENDIENTE')
        self.remote.assert_not_called()
        with self.assertRaises(ValueError):
            CajaManager.cerrar_caja(90)
        self.assertEqual(len(self.sql('SELECT * FROM sync_cierres')), 1)

    def test_close_and_outbox_rollback_together_on_storage_failure(self):
        CajaManager.abrir_caja(100)
        self.sql("CREATE TRIGGER fail_outbox BEFORE INSERT ON sync_cierres BEGIN SELECT RAISE(ABORT, 'storage unavailable'); END")
        with self.assertRaises(Exception):
            CajaManager.cerrar_caja(100)
        row = self.sql('SELECT estado, cierre_usuario_id, monto_cierre FROM caja_sesiones')[0]
        self.assertEqual(row, {'estado': 'ABIERTA', 'cierre_usuario_id': None, 'monto_cierre': None})
        self.assertEqual(self.sql('SELECT * FROM sync_cierres'), [])

    def test_other_operator_and_branch_cannot_operate_the_open_turn(self):
        caja = CajaManager.abrir_caja(100)
        self.user.user_id = '22222222-2222-4222-8222-222222222222'
        for operation in (lambda: CajaManager.cerrar_caja(100),
                          lambda: CajaManager.registrar_movimiento(caja, 'EGRESO', 1, 'EFECTIVO'),
                          lambda: VentasManager.procesar_venta(1, 'EFECTIVO', [])):
            with self.assertRaises(ValueError):
                operation()
        self.user.role = 'admin'
        self.user.branch_id = '33333333-3333-4333-8333-333333333333'
        with self.assertRaises(ValueError):
            CajaManager.cerrar_caja(100)

    def test_admin_can_close_in_same_branch_without_replacing_owner(self):
        CajaManager.abrir_caja(100)
        original = self.user.user_id
        self.user.user_id = '22222222-2222-4222-8222-222222222222'
        self.user.username = 'encargado'
        self.user.role = 'admin'
        CajaManager.cerrar_caja(100)
        row = self.sql('SELECT responsable_id, cierre_usuario_id FROM caja_sesiones')[0]
        self.assertEqual(row['responsable_id'], original)
        self.assertEqual(row['cierre_usuario_id'], self.user.user_id)

    def test_authentication_is_required_for_cash_and_sales(self):
        self.require.side_effect = RuntimeError('Debe iniciar sesión')
        for operation in (lambda: CajaManager.abrir_caja(100),
                          lambda: CajaManager.cerrar_caja(100),
                          lambda: VentasManager.procesar_venta(1, 'EFECTIVO', [])):
            with self.assertRaisesRegex(RuntimeError, 'iniciar sesión'):
                operation()
        self.assertEqual(self.sql('SELECT * FROM ventas'), [])

    def test_legacy_open_cash_is_not_assigned_to_current_user(self):
        self.sql("INSERT INTO caja_sesiones(monto_inicial, estado) VALUES (100, 'ABIERTA')")
        database.init_db()
        database.init_db()
        for operation in (CajaManager.obtener_sesion_activa,
                          lambda: CajaManager.cerrar_caja(100),
                          lambda: VentasManager.procesar_venta(1, 'EFECTIVO', [])):
            with self.assertRaisesRegex(ValueError, 'sin responsable'):
                operation()
        self.assertIsNone(self.sql('SELECT responsable_id FROM caja_sesiones')[0]['responsable_id'])
        self.assertEqual(self.sql('SELECT * FROM sync_cierres'), [])

    def test_amounts_must_be_finite_and_nonnegative(self):
        for value in (-1, float('nan'), float('inf'), 'invalid'):
            with self.assertRaises(ValueError):
                CajaManager.abrir_caja(value)
        CajaManager.abrir_caja(0)
        with self.assertRaises(ValueError):
            CajaManager.cerrar_caja(float('nan'))

    def test_lost_ack_retries_same_immutable_snapshot_without_duplicate_remote_close(self):
        CajaManager.abrir_caja(100)
        CajaManager.cerrar_caja(100)
        server = {}

        def lost_ack(method, path, payload=None, **kwargs):
            if method == 'GET':
                return []
            if '/rpc/sincronizar_entidades' in path:
                return {'acknowledged': [event['id'] for event in payload['p_eventos']]}
            server.setdefault(payload['id'], payload)
            raise NetworkError('Sin conexión')

        self.remote.side_effect = lost_ack
        first = SyncManager.sync_pending()
        self.assertEqual((first['sent'], first['pending']), (0, 1))
        outbox = self.sql('SELECT * FROM sync_cierres')[0]
        self.assertEqual(outbox['intentos'], 1)

        def acknowledged(method, path, payload=None, **kwargs):
            if method == 'GET':
                return []
            if '/rpc/sincronizar_entidades' in path:
                return {'acknowledged': [event['id'] for event in payload['p_eventos']]}
            self.assertEqual(kwargs['headers']['Prefer'], 'resolution=ignore-duplicates,return=minimal')
            server.setdefault(payload['id'], payload)

        self.remote.side_effect = acknowledged
        second = SyncManager.sync_pending()
        self.assertEqual((second['sent'], second['pending']), (1, 0))
        self.assertEqual(len(server), 1)
        self.assertEqual(json.loads(outbox['payload']), next(iter(server.values())))
        self.assertEqual(self.sql('SELECT estado FROM sync_cierres')[0]['estado'], 'ENVIADO')

    def test_pending_close_is_not_sent_with_another_operators_session(self):
        CajaManager.abrir_caja(100)
        CajaManager.cerrar_caja(100)
        self.user.user_id = '22222222-2222-4222-8222-222222222222'
        self.remote.side_effect = lambda method, path, payload=None, **kwargs: [] if method == 'GET' else {'acknowledged': []}
        result = SyncManager.sync_pending()
        self.assertEqual((result['sent'], result['pending']), (0, 1))
        self.assertFalse(any('/cierres_caja' in call.args[1] for call in self.remote.call_args_list))
        self.token.assert_called_once()  # Puede informar conexión sin enviar cierres ajenos.


if __name__ == '__main__':
    unittest.main()
