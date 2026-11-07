import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from types import SimpleNamespace
import unittest
from unittest.mock import patch, Mock

from PyQt6.QtWidgets import QApplication, QMessageBox

from src.core.caja_manager import CajaAnteriorError
from src.ui.caja_view import CajaView
from src.ui.sync_controller import SyncController


class LegacyCashUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.previous = [{'id': 47, 'fecha_apertura': '2026-06-01 08:00:00'}]
        self.getter = patch('src.ui.caja_view.CajaManager.obtener_sesion_activa', side_effect=CajaAnteriorError('Caja anterior'))
        self.getter.start()
        self.addCleanup(self.getter.stop)
        self.legacy = patch('src.ui.caja_view.CajaManager.obtener_cajas_anteriores', return_value=self.previous)
        self.legacy.start()
        self.addCleanup(self.legacy.stop)
        self.identity = patch('src.ui.caja_view.AuthManager.require_user', return_value=SimpleNamespace(username='caja1'))
        self.identity.start()
        self.addCleanup(self.identity.stop)
        self.close = patch('src.ui.caja_view.CajaManager.cerrar_caja_anterior')
        self.close_call = self.close.start()
        self.addCleanup(self.close.stop)
        self.widget = CajaView()
        self.addCleanup(self.widget.deleteLater)

    def test_cancel_cash_count_does_not_modify_history(self):
        self.assertFalse(self.widget.btn_cerrar_anterior.isHidden())
        with patch('src.ui.caja_view.QInputDialog.getDouble', return_value=(0, False)), \
                patch('src.ui.caja_view.QInputDialog.getMultiLineText') as reason:
            self.widget.cerrar_caja_anterior()
        reason.assert_not_called()
        self.close_call.assert_not_called()

    def test_reason_must_be_supplied_before_closing(self):
        with patch('src.ui.caja_view.QInputDialog.getDouble', return_value=(50, True)), \
                patch('src.ui.caja_view.QInputDialog.getMultiLineText', return_value=('corto', True)), \
                patch('src.ui.caja_view.QMessageBox.warning') as warning:
            self.widget.cerrar_caja_anterior()
        warning.assert_called_once()
        self.close_call.assert_not_called()

    def test_cancel_confirmation_does_not_close(self):
        with patch('src.ui.caja_view.QInputDialog.getDouble', return_value=(50, True)), \
                patch('src.ui.caja_view.QInputDialog.getMultiLineText', return_value=('Transición de versión', True)), \
                patch('src.ui.caja_view.CajaManager.obtener_resumen', return_value={'total_efectivo_esperado': 100}), \
                patch('src.ui.caja_view.QMessageBox.question', return_value=QMessageBox.StandardButton.No):
            self.widget.cerrar_caja_anterior()
        self.close_call.assert_not_called()

    def test_success_displays_backup_and_enables_new_turn_without_cloud_signal(self):
        self.close_call.return_value = {
            'caja_id': 47, 'contado': 50, 'esperado': 100, 'diferencia': -50,
            'backup_path': 'respaldo-previo.sqlite',
        }
        sync_signal = Mock()
        self.widget.caja_cerrada.connect(sync_signal)
        with patch('src.ui.caja_view.QInputDialog.getDouble', return_value=(50, True)) as count, \
                patch('src.ui.caja_view.QInputDialog.getMultiLineText', return_value=('  Transición de versión  ', True)), \
                patch('src.ui.caja_view.CajaManager.obtener_resumen', return_value={'total_efectivo_esperado': 100}), \
                patch('src.ui.caja_view.QMessageBox.question', return_value=QMessageBox.StandardButton.Yes) as confirm, \
                patch('src.ui.caja_view.QMessageBox.information') as information, \
                patch('src.ui.caja_view.CajaManager.obtener_sesion_activa', return_value=None):
            self.widget.cerrar_caja_anterior()
        self.assertEqual(count.call_args.args[3], 0.0)
        self.close_call.assert_called_once_with(47, 50, 'Transición de versión')
        text = confirm.call_args.args[2]
        self.assertIn('No registrado (versión anterior)', text)
        self.assertIn('caja1', text)
        self.assertIn('$-50.00', text)
        self.assertIn('respaldo-previo.sqlite', information.call_args.args[2])
        self.assertFalse(self.widget.frame_apertura.isHidden())
        self.assertTrue(self.widget.frame_bloqueo.isHidden())
        sync_signal.assert_not_called()

    def test_foreign_or_partial_metadata_does_not_offer_legacy_bypass(self):
        with patch('src.ui.caja_view.CajaManager.obtener_sesion_activa', side_effect=ValueError('Otra persona o metadatos incompletos')), \
                patch('src.ui.caja_view.CajaManager.obtener_cajas_anteriores') as list_legacy:
            self.widget.actualizar_estado()
        list_legacy.assert_not_called()
        self.assertTrue(self.widget.btn_cerrar_anterior.isHidden())
        self.assertIn('metadatos incompletos', self.widget.lbl_bloqueo.text())

    def test_multiple_previous_turns_require_the_selected_id(self):
        self.previous.append({'id': 48, 'fecha_apertura': '2026-06-02 09:00:00'})
        self.widget.actualizar_estado()
        self.widget.cb_cajas_anteriores.setCurrentIndex(1)
        with patch('src.ui.caja_view.QInputDialog.getDouble', return_value=(0, False)) as count:
            self.widget.cerrar_caja_anterior()
        self.assertIn('Turno #48', count.call_args.args[2])
        self.close_call.assert_not_called()

    def test_empty_queue_status_does_not_claim_online_verification(self):
        controller = SyncController()
        controller.stop()
        controller.worker = Mock(result={'sent': 0, 'pending': 0, 'error': None})
        status = Mock()
        controller.status_changed.connect(status)
        controller.finished()
        status.assert_called_once_with('No hay operaciones pendientes de envío')
        controller.deleteLater()


if __name__ == '__main__':
    unittest.main()
