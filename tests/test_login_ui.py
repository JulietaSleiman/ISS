import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from types import SimpleNamespace
import unittest
from unittest.mock import patch, Mock

from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox

from src.ui.login_dialog import LoginDialog
from src.ui.caja_view import CajaView
from src.ui.main_window import MainWindow
from src.ui.sync_controller import SyncController


class LoginUI(unittest.TestCase):
    def setUp(self):
        installation = patch('src.ui.login_dialog.get_installation', return_value={
            'branch_id': 'simoca', 'branch_code': 'estacion-de-simoca',
            'branch_name': 'Estación de Simoca', 'project_url': 'https://example.invalid', 'legacy': False,
        })
        installation.start()
        self.addCleanup(installation.stop)

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def wait_for_login(self, dialog):
        for _ in range(200):
            self.app.processEvents()
            if dialog.worker is None:
                return
            QTest.qWait(5)
        self.fail('El hilo de acceso no finalizó')

    def test_cancelled_login_does_not_accept(self):
        dialog = LoginDialog()
        dialog.reject()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)

    def test_wrong_password_never_opens_the_operating_window(self):
        dialog = LoginDialog()
        dialog.password.setText('incorrecta')
        with patch('src.ui.login_dialog.AuthManager.login', side_effect=ValueError('Credenciales inválidas')):
            dialog.start_login()
            self.wait_for_login(dialog)
        self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)
        self.assertEqual(dialog.password.text(), '')
        self.assertIn('Credenciales inválidas', dialog.message.text())
        self.assertTrue(dialog.login_button.isEnabled())

    def test_verified_login_completes_after_worker_finishes(self):
        dialog = LoginDialog()
        session = SimpleNamespace(username='caja1', offline=True)
        dialog.password.setText('no-se-guarda')
        with patch('src.ui.login_dialog.AuthManager.login', return_value=session) as login:
            dialog.start_login()
            self.wait_for_login(dialog)
        login.assert_called_once_with('caja1', 'no-se-guarda')
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(dialog.password.text(), '')

    def test_close_uses_counted_cash_and_displays_difference(self):
        active = {'id': 1, 'fecha_apertura': '2026-01-01 09:00:00', 'responsable_nombre': 'caja1'}
        summary = {'monto_inicial': 100, 'total_efectivo_esperado': 100}
        with patch('src.ui.caja_view.CajaManager.obtener_sesion_activa', return_value=active), \
                patch('src.ui.caja_view.CajaManager.obtener_resumen', return_value=summary), \
                patch('src.ui.caja_view.CajaManager.obtener_movimientos', return_value=[]):
            widget = CajaView()
            with patch('src.ui.caja_view.AuthManager.require_user', return_value=SimpleNamespace(username='caja1')), \
                    patch('src.ui.caja_view.QInputDialog.getDouble', return_value=(80.0, True)) as count, \
                    patch('src.ui.caja_view.QMessageBox.question', return_value=QMessageBox.StandardButton.Yes) as confirm, \
                    patch('src.ui.caja_view.CajaManager.cerrar_caja', return_value={'monto_cierre': 80, 'diferencia': -20}) as close, \
                    patch('src.ui.caja_view.QMessageBox.information'):
                widget.cerrar_caja()
            self.assertEqual(count.call_args.args[3], 0.0)
            close.assert_called_once_with(80.0)
            self.assertIn('Diferencia: $-20.00', confirm.call_args.args[2])
            self.assertIn('caja1', confirm.call_args.args[2])
            widget.deleteLater()

    def test_cancelled_cash_count_does_not_close_turn(self):
        with patch('src.ui.caja_view.CajaManager.obtener_sesion_activa', return_value=None):
            widget = CajaView()
        widget.sesion_activa = {'id': 1}
        with patch('src.ui.caja_view.AuthManager.require_user', return_value=SimpleNamespace(username='caja1')), \
                patch('src.ui.caja_view.QInputDialog.getDouble', return_value=(0, False)), \
                patch('src.ui.caja_view.CajaManager.cerrar_caja') as close:
            widget.cerrar_caja()
            close.assert_not_called()
        widget.deleteLater()

    def test_legacy_open_turn_disables_operating_controls(self):
        with patch('src.ui.caja_view.CajaManager.obtener_sesion_activa', side_effect=ValueError('Cierre la caja en la versión anterior')):
            widget = CajaView()
        self.assertTrue(widget.frame_apertura.isHidden())
        self.assertTrue(widget.frame_movimientos.isHidden())
        self.assertIn('versión anterior', widget.lbl_bloqueo.text())
        self.assertTrue(widget.btn_cerrar_anterior.isHidden())
        widget.deleteLater()

    def test_logout_blocked_while_cash_turn_is_open(self):
        window = SimpleNamespace(login_again=False, close=Mock())
        with patch('src.ui.main_window.CajaManager.obtener_sesion_activa', return_value={'id': 1}), \
                patch('src.ui.main_window.QMessageBox.warning'):
            MainWindow.cerrar_sesion(window)
        window.close.assert_not_called()
        self.assertFalse(window.login_again)

    def test_revoked_session_blocks_ui_before_reauthentication(self):
        central = Mock()
        window = SimpleNamespace(_close_requested=False, login_again=False, centralWidget=lambda: central, close=Mock())
        with patch('src.ui.main_window.AuthManager.current_user', return_value=None), \
                patch('src.ui.main_window.QMessageBox.warning'):
            MainWindow._check_session(window)
        central.setEnabled.assert_called_once_with(False)
        self.assertTrue(window.login_again)
        window.close.assert_called_once()

    def test_reconnected_session_updates_connection_indicator(self):
        session = SimpleNamespace(branch_name='Estación de Simoca', username='caja1', offline=False)
        window = SimpleNamespace(lbl_user=Mock())
        with patch('src.ui.main_window.AuthManager.current_user', return_value=session):
            MainWindow._check_session(window)
        self.assertIn('Acceso verificado', window.lbl_user.setText.call_args.args[0])

    def test_sync_does_not_start_overlapping_uploads(self):
        controller = SyncController()
        with patch('src.ui.sync_controller.SyncWorker') as worker:
            controller.start()
            controller.start()
            worker.assert_called_once()
        controller.stop()
        controller.worker = None
        controller.deleteLater()


if __name__ == '__main__':
    unittest.main()
