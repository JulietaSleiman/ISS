import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from threading import Event
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PyQt6.QtGui import QCloseEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QDialog

from src.ui.login_dialog import LoginDialog, LoginWorker


class BranchSetupUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def dialog(self, installation=None, error=None):
        with patch('src.ui.login_dialog.get_installation', return_value=installation, side_effect=error):
            dialog = LoginDialog()
        self.addCleanup(dialog.deleteLater)
        return dialog

    def wait(self, dialog):
        for _ in range(200):
            self.app.processEvents()
            if dialog.worker is None:
                return
            QTest.qWait(5)
        self.fail('El hilo de acceso no finalizó')

    def credentials(self, dialog):
        dialog.username.setText('caja1')
        dialog.password.setText('secreto')

    def test_new_computer_has_no_implicit_branch(self):
        dialog = self.dialog()
        self.assertEqual(dialog.windowTitle(), 'Configurar esta computadora')
        self.assertEqual(dialog.branch_code.text(), '')
        self.assertEqual(dialog.branch_code.placeholderText(), 'estacion-de-simoca')
        self.assertFalse(dialog.branch_code.isReadOnly())
        self.assertEqual(dialog.login_button.text(), 'Vincular e ingresar')
        self.credentials(dialog)
        with patch('src.ui.login_dialog.AuthManager.login') as login:
            dialog.start_login()
            login.assert_not_called()
        self.assertIn('código de sucursal', dialog.message.text())

    def test_setup_passes_explicit_code_and_accepts_verified_session(self):
        dialog = self.dialog()
        self.credentials(dialog)
        dialog.branch_code.setText(' sucursal-nueva ')
        with patch('src.ui.login_dialog.AuthManager.login', return_value=SimpleNamespace(username='caja1')) as login:
            dialog.start_login()
            self.wait(dialog)
        login.assert_called_once_with('caja1', 'secreto', 'sucursal-nueva')
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(dialog.password.text(), '')

    def test_setup_network_or_credentials_failure_never_accepts(self):
        for error in ('Sin conexión: primera vinculación requiere internet', 'Código o usuario inválido'):
            with self.subTest(error=error):
                dialog = self.dialog()
                self.credentials(dialog)
                dialog.branch_code.setText('otro-local')
                with patch('src.ui.login_dialog.AuthManager.login', side_effect=ValueError(error)):
                    dialog.start_login()
                    self.wait(dialog)
                self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)
                self.assertEqual(dialog.password.text(), '')
                self.assertIn(error, dialog.message.text())
                self.assertTrue(dialog.branch_code.isEnabled())

    def test_linked_and_legacy_installations_use_saved_identity_and_two_args(self):
        for legacy in (False, True):
            with self.subTest(legacy=legacy), patch.dict(os.environ, {'ISS_BRANCH_NAME': 'Incorrecta', 'ISS_BRANCH_CODE': 'incorrecta'}):
                dialog = self.dialog({
                    'branch_id': 'saved-id', 'branch_code': 'guardada',
                    'branch_name': 'Sucursal guardada', 'project_url': 'https://example.invalid', 'legacy': legacy,
                })
                self.assertEqual(dialog.title.text(), 'Sucursal guardada')
                self.assertEqual(dialog.branch_code.text(), 'guardada')
                self.assertTrue(dialog.branch_code.isReadOnly())
                self.assertEqual(dialog.windowTitle(), 'Iniciar sesión')
                self.credentials(dialog)
                with patch('src.ui.login_dialog.AuthManager.login', return_value=SimpleNamespace(username='caja1')) as login:
                    dialog.start_login()
                    self.wait(dialog)
                login.assert_called_once_with('caja1', 'secreto')

    def test_installation_read_failure_blocks_login_instead_of_defaulting(self):
        dialog = self.dialog(error=ValueError('Metadatos inválidos'))
        self.credentials(dialog)
        dialog.branch_code.setText('estacion-de-simoca')
        self.assertFalse(dialog.login_button.isEnabled())
        self.assertIn('Metadatos inválidos', dialog.message.text())
        with patch('src.ui.login_dialog.AuthManager.login') as login:
            dialog.start_login()
            login.assert_not_called()

    def test_cancel_before_setup_does_not_authenticate(self):
        dialog = self.dialog()
        with patch('src.ui.login_dialog.AuthManager.login') as login:
            dialog.reject()
            login.assert_not_called()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)

    def test_pending_setup_disables_fields_and_guards_close(self):
        dialog = self.dialog()
        self.credentials(dialog)
        dialog.branch_code.setText('otra')
        release = Event()
        def pending(*args):
            release.wait(3)
            raise ValueError('Sin conexión')
        with patch('src.ui.login_dialog.AuthManager.login', side_effect=pending):
            dialog.start_login()
            try:
                self.assertFalse(dialog.branch_code.isEnabled())
                self.assertFalse(dialog.buttons.isEnabled())
                worker = dialog.worker
                dialog.start_login()
                self.assertIs(dialog.worker, worker)
                dialog.reject()
                event = QCloseEvent()
                dialog.closeEvent(event)
                self.assertFalse(event.isAccepted())
                self.assertIsNotNone(dialog.worker)
            finally:
                release.set()
                self.wait(dialog)
        self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)
        self.assertTrue(dialog.login_button.isEnabled())

    def test_worker_parent_position_remains_compatible_and_clears_password(self):
        dialog = self.dialog()
        worker = LoginWorker('caja1', 'secreto', dialog)
        with patch('src.ui.login_dialog.AuthManager.login', return_value=None) as login:
            worker.run()
        login.assert_called_once_with('caja1', 'secreto')
        self.assertIs(worker.parent(), dialog)
        self.assertIsNone(worker.password)


if __name__ == '__main__':
    unittest.main()
