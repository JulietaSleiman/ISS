from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from src.core.auth_manager import AuthManager
from src.core.caja_manager import CajaAnteriorError, CajaManager
from src.db import database


class LegacyCashTransitionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(temp.cleanup)
        self.db_path = Path(temp.name) / 'test.sqlite'
        self.user = SimpleNamespace(
            user_id='11111111-1111-4111-8111-111111111111', username='caja1',
            branch_id='f2985c88-2a4e-4e73-92d5-85d905b3db41', role='cajero')
        for target, value in (
            ('src.db.database.DB_PATH', self.db_path),
            ('src.db.database.auto_backup_db', lambda: None),
        ):
            patcher = patch(target, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch.object(AuthManager, 'require_user', return_value=self.user)
        self.auth = patcher.start()
        self.addCleanup(patcher.stop)
        database.init_db()
        self.first = self.insert_legacy(100)
        self.second = self.insert_legacy(200)
        self.sql("INSERT INTO ventas(cliente_id,caja_sesion_id,subtotal,total,metodo_pago) VALUES (1,?,40,40,'EFECTIVO')", (self.first,))
        self.sql("INSERT INTO caja_movimientos(caja_sesion_id,tipo,monto,metodo_pago,descripcion) VALUES (?,'EGRESO',10,'EFECTIVO','Retiro histórico')", (self.first,))

    def sql(self, query, params=()):
        with closing(database.get_connection()) as conn:
            with conn:
                return [dict(row) for row in conn.execute(query, params).fetchall()]

    def insert_legacy(self, monto):
        with closing(database.get_connection()) as conn:
            with conn:
                return conn.execute("INSERT INTO caja_sesiones(monto_inicial,estado,fecha_apertura) VALUES (?,'ABIERTA','2026-06-15 12:00:00')", (monto,)).lastrowid

    def close_first(self):
        return CajaManager.cerrar_caja_anterior(self.first, 125, 'Transición al sistema con usuarios')

    def test_selected_legacy_close_preserves_original_data_and_audits_actor(self):
        before = self.sql('SELECT * FROM caja_sesiones ORDER BY id')
        ventas_before = self.sql('SELECT * FROM ventas')
        movimientos_before = self.sql('SELECT * FROM caja_movimientos')
        result = self.close_first()
        self.assertEqual((result['esperado'], result['contado'], result['diferencia']), (130, 125, -5))
        rows = self.sql('SELECT * FROM caja_sesiones ORDER BY id')
        first, second = rows
        self.assertEqual(first['estado'], 'CERRADA')
        self.assertEqual(first['cierre_usuario_id'], self.user.user_id)
        self.assertEqual(first['cierre_usuario_nombre'], 'caja1')
        for key in ('responsable_id', 'responsable_nombre', 'sucursal_id', 'sync_id'):
            self.assertIsNone(first[key])
        self.assertEqual(first['fecha_apertura'], before[0]['fecha_apertura'])
        self.assertEqual(second, before[1])
        self.assertEqual(self.sql('SELECT * FROM ventas'), ventas_before)
        self.assertEqual(self.sql('SELECT * FROM caja_movimientos'), movimientos_before)
        self.assertEqual(self.sql('SELECT * FROM sync_cierres'), [])
        audit = self.sql('SELECT * FROM caja_regularizaciones')[0]
        self.assertEqual(audit['caja_id'], self.first)
        self.assertEqual(audit['usuario_id'], self.user.user_id)
        self.assertEqual(audit['sucursal_id'], self.user.branch_id)
        self.assertEqual(audit['motivo'], 'Transición al sistema con usuarios')
        self.assertEqual(audit['backup_path'], result['backup_path'])
        self.assertEqual([r['id'] for r in CajaManager.obtener_cajas_anteriores()], [self.second])

    def test_backup_contains_original_open_turn_and_original_sales(self):
        result = self.close_first()
        backup_path = Path(result['backup_path'])
        self.assertEqual(backup_path.parent, self.db_path.parent / 'Backups_Transicion')
        self.assertTrue(backup_path.is_file())
        with closing(sqlite3.connect(backup_path)) as backup:
            row = backup.execute('SELECT estado,monto_cierre,responsable_id,cierre_usuario_id FROM caja_sesiones WHERE id=?', (self.first,)).fetchone()
            self.assertEqual(row, ('ABIERTA', None, None, None))
            self.assertEqual(backup.execute('SELECT COUNT(*) FROM caja_regularizaciones').fetchone()[0], 0)
            self.assertEqual(backup.execute('SELECT total FROM ventas WHERE caja_sesion_id=?', (self.first,)).fetchone()[0], 40)

    def test_backup_failure_aborts_all_changes(self):
        before = self.sql('SELECT * FROM caja_sesiones ORDER BY id')
        with patch.object(CajaManager, '_respaldar_transicion', side_effect=OSError('No se pudo crear el respaldo')):
            with self.assertRaisesRegex(OSError, 'respaldo'):
                self.close_first()
        self.assertEqual(self.sql('SELECT * FROM caja_sesiones ORDER BY id'), before)
        self.assertEqual(self.sql('SELECT * FROM caja_regularizaciones'), [])

    def test_audit_failure_rolls_back_close_and_keeps_backup(self):
        self.sql("CREATE TRIGGER fail_audit BEFORE INSERT ON caja_regularizaciones BEGIN SELECT RAISE(ABORT, 'Audit storage unavailable'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.close_first()
        self.assertEqual(self.sql('SELECT estado FROM caja_sesiones WHERE id=?', (self.first,))[0]['estado'], 'ABIERTA')
        self.assertEqual(self.sql('SELECT * FROM caja_regularizaciones'), [])
        backups = list((self.db_path.parent / 'Backups_Transicion').glob('*.sqlite'))
        self.assertEqual(len(backups), 1)
        with closing(sqlite3.connect(backups[0])) as backup:
            self.assertEqual(backup.execute('SELECT estado FROM caja_sesiones WHERE id=?', (self.first,)).fetchone()[0], 'ABIERTA')

    def test_same_turn_cannot_be_closed_twice_or_make_another_backup(self):
        self.close_first()
        with patch.object(CajaManager, '_respaldar_transicion') as backup:
            with self.assertRaisesRegex(ValueError, 'ya fue cerrada'):
                self.close_first()
            backup.assert_not_called()
        self.assertEqual(len(self.sql('SELECT * FROM caja_regularizaciones')), 1)

    def test_validates_identity_counted_money_and_explanation(self):
        for invalid in (-1, float('nan'), float('inf'), 'incorrecto'):
            with self.assertRaises(ValueError):
                CajaManager.cerrar_caja_anterior(self.first, invalid, 'Transición por instalación')
        for invalid in ('', 'corto', '          ', None):
            with self.assertRaisesRegex(ValueError, '10 caracteres'):
                CajaManager.cerrar_caja_anterior(self.first, 100, invalid)
        self.auth.side_effect = RuntimeError('Debe iniciar sesión')
        with self.assertRaisesRegex(RuntimeError, 'iniciar sesión'):
            self.close_first()
        with self.assertRaisesRegex(RuntimeError, 'iniciar sesión'):
            CajaManager.obtener_cajas_anteriores()
        self.assertEqual(self.sql('SELECT * FROM caja_regularizaciones'), [])

    def test_partial_identity_is_not_a_legacy_bypass(self):
        self.sql('UPDATE caja_sesiones SET sucursal_id=? WHERE id=?', (self.user.branch_id, self.first))
        self.sql("UPDATE caja_sesiones SET responsable_id='' WHERE id=?", (self.second,))
        self.assertEqual(CajaManager.obtener_cajas_anteriores(), [])
        with self.assertRaisesRegex(ValueError, 'incompletos') as error:
            CajaManager.obtener_sesion_activa()
        self.assertNotIsInstance(error.exception, CajaAnteriorError)
        with patch.object(CajaManager, '_respaldar_transicion') as backup:
            for caja in (self.first, self.second):
                with self.assertRaises(ValueError):
                    CajaManager.cerrar_caja_anterior(caja, 100, 'Transición por instalación')
            backup.assert_not_called()

    def test_transition_allows_a_new_identified_turn_after_all_legacy_are_closed(self):
        with self.assertRaises(CajaAnteriorError):
            CajaManager.abrir_caja(100)
        self.close_first()
        with self.assertRaises(CajaAnteriorError):
            CajaManager.abrir_caja(100)
        CajaManager.cerrar_caja_anterior(self.second, 200, 'Transición del segundo turno anterior')
        database.init_db()
        database.init_db()
        nueva = CajaManager.abrir_caja(100)
        row = self.sql('SELECT responsable_id,sucursal_id,sync_id FROM caja_sesiones WHERE id=?', (nueva,))[0]
        self.assertEqual(row['responsable_id'], self.user.user_id)
        self.assertEqual(row['sucursal_id'], self.user.branch_id)
        self.assertIsNotNone(row['sync_id'])
        self.assertEqual(len(self.sql('SELECT * FROM caja_regularizaciones')), 2)


if __name__ == '__main__':
    unittest.main()
