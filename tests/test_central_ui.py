import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from PyQt6.QtCore import QDate, QTimer
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QMessageBox

from src.ui.central_view import CentralView
from src.ui.main_window import MainWindow


class CentralUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.user = SimpleNamespace(user_id='admin-id', role='admin')
        self.require = patch('src.ui.central_view.AuthManager.require_user', side_effect=lambda: self.user)
        self.current = patch('src.ui.central_view.AuthManager.current_user', side_effect=lambda: self.user)
        self.require.start()
        self.current.start()
        self.addCleanup(self.require.stop)
        self.addCleanup(self.current.stop)
        self.product = {
            'id': 'product-uuid', 'local_id': 3, 'sucursal_id': 'branch-id',
            'sucursal_nombre': 'Estación de Simoca', 'nombre': 'Producto de prueba',
            'codigo_barras': '123', 'stock_actual': 15, 'stock_minimo': 5,
            'precio_contado': 100, 'precio_tarjeta': 110, 'catalog_revision': 7,
        }
        self.dashboard = {
            'branches': [{'id': 'branch-id', 'nombre': 'Estación de Simoca',
                          'last_sync_at': '2026-11-06T16:00:00Z', 'pendientes': 25,
                          'total_vendido': 999, 'ventas_count': 30, 'productos_count': 125,
                          'alertas_stock': 4, 'cierres_count': 2, 'diferencias': -10}],
            'totals': {'total_vendido': 999, 'ventas_count': 30, 'productos_count': 125,
                       'alertas_stock': 4, 'cierres_count': 2, 'diferencias': -10},
            'fetched_at': '2026-11-06T16:05:00Z',
        }
        self.page = {'rows': [self.product], 'has_more': True}
        self.widget = None

    def tearDown(self):
        if self.widget is not None:
            self.wait_for_worker()
            self.widget.stop()
            self.widget.deleteLater()
            self.app.processEvents()

    def new_widget(self):
        self.widget = CentralView()
        return self.widget

    def wait_for_worker(self):
        for _ in range(400):
            self.app.processEvents()
            if self.widget is None or not self.widget.is_running():
                return
            QTest.qWait(5)
        self.fail('La consulta central no finalizó')

    def populated(self):
        widget = self.new_widget()
        widget._show_result({'dashboard': self.dashboard, 'page': self.page}, 'productos')
        widget.tables['productos'].selectRow(0)
        widget._update_buttons()
        return widget

    def test_cashier_cannot_construct_central_view(self):
        self.user.role = 'cajero'
        with self.assertRaises(PermissionError), patch('src.ui.central_view.CentralManager.fetch_dashboard') as query:
            CentralView()
        query.assert_not_called()

    def test_filters_and_paging_are_sent_to_server_and_totals_are_not_page_sums(self):
        widget = self.new_widget()
        widget.branch.addItem('Estación de Simoca', 'branch-id')
        widget.branch.setCurrentIndex(1)
        widget.date_from.setDate(QDate(2026, 11, 1))
        widget.date_to.setDate(QDate(2026, 11, 6))
        with patch('src.ui.central_view.CentralManager.fetch_dashboard', return_value=self.dashboard), \
                patch('src.ui.central_view.CentralManager.fetch_page', side_effect=[self.page, {'rows': [], 'has_more': False}]) as query:
            widget.refresh()
            self.wait_for_worker()
            self.assertIn('$999,00', widget.summary.text())
            self.assertIn('125', widget.summary.text())
            self.assertEqual(widget.branches_table.item(0, 2).text(), '25')
            query.assert_called_with('productos', branch_id='branch-id', fecha_desde='2026-11-01', fecha_hasta='2026-11-06', page=0, page_size=100)
            widget.change_page(1)
            self.wait_for_worker()
            self.assertEqual(query.call_args.kwargs['page'], 1)
            self.assertFalse(widget.next_button.isEnabled())
            self.assertTrue(widget.previous_button.isEnabled())

    def test_network_work_does_not_block_ui_event_processing(self):
        widget = self.new_widget()
        release = threading.Event()
        self.addCleanup(release.set)
        processed = []

        def fetch(**kwargs):
            release.wait(1)
            return self.dashboard

        with patch('src.ui.central_view.CentralManager.fetch_dashboard', side_effect=fetch), \
                patch('src.ui.central_view.CentralManager.fetch_page', return_value=self.page):
            widget.refresh()
            QTimer.singleShot(0, lambda: processed.append(True))
            self.app.processEvents()
            self.assertTrue(widget.is_running())
            self.assertEqual(processed, [True])
            release.set()
            self.wait_for_worker()

    def test_stale_response_is_discarded_after_filter_changes(self):
        widget = self.new_widget()
        release = threading.Event()
        self.addCleanup(release.set)

        def fetch(**kwargs):
            release.wait(1)
            return self.dashboard

        with patch('src.ui.central_view.CentralManager.fetch_dashboard', side_effect=fetch), \
                patch('src.ui.central_view.CentralManager.fetch_page', return_value=self.page):
            widget.refresh()
            widget.date_from.setDate(widget.date_from.date().addDays(-1))
            release.set()
            self.wait_for_worker()
        self.assertFalse(widget.valid_snapshot)
        self.assertEqual(widget.tables['productos'].rowCount(), 0)
        self.assertIn('descartó una respuesta anterior', widget.status.text())

    def test_network_error_labels_previous_data_and_disables_price_action(self):
        widget = self.populated()
        with patch('src.ui.central_view.CentralManager.fetch_dashboard', side_effect=ValueError('Sin conexión')):
            widget.refresh()
            self.wait_for_worker()
        self.assertIn('No se pudo actualizar', widget.status.text())
        self.assertIn('anteriores', widget.status.text())
        self.assertFalse(widget.price_button.isEnabled())

    def test_cancelled_price_input_does_not_create_command(self):
        widget = self.populated()
        with patch('src.ui.central_view.QInputDialog.getDouble', return_value=(0, False)), \
                patch('src.ui.central_view.CentralManager.request_price_change') as command:
            widget.request_price_change()
        command.assert_not_called()

    def test_declined_confirmation_does_not_create_command(self):
        widget = self.populated()
        with patch('src.ui.central_view.QInputDialog.getDouble', side_effect=[(120, True), (130, True)]), \
                patch('src.ui.central_view.QMessageBox.question', return_value=QMessageBox.StandardButton.No), \
                patch('src.ui.central_view.CentralManager.request_price_change') as command:
            widget.request_price_change()
        command.assert_not_called()

    def test_confirmed_price_change_carries_revision_and_remains_pending(self):
        widget = self.populated()
        with patch('src.ui.central_view.QInputDialog.getDouble', side_effect=[(120, True), (130, True)]), \
                patch('src.ui.central_view.QMessageBox.question', return_value=QMessageBox.StandardButton.Yes) as confirm, \
                patch('src.ui.central_view.QMessageBox.information'), \
                patch('src.ui.central_view.CentralManager.request_price_change', return_value={'estado': 'PENDIENTE'}) as command:
            widget.request_price_change()
            self.wait_for_worker()
        command.assert_called_once_with(branch_id='branch-id', product_id='product-uuid', expected_catalog_revision=7, precio_contado=120, precio_tarjeta=130)
        self.assertIn('Estación de Simoca', confirm.call_args.args[2])
        self.assertIn('Pendiente de confirmación', widget.status.text())
        self.assertEqual(widget.tables['productos'].item(0, 5).text(), '$100,00')

    def test_invalid_prices_are_rejected_before_remote_request(self):
        widget = self.populated()
        with patch('src.ui.central_view.QInputDialog.getDouble', side_effect=[(float('nan'), True), (130, True)]), \
                patch('src.ui.central_view.QMessageBox.warning'), \
                patch('src.ui.central_view.CentralManager.request_price_change') as command:
            widget.request_price_change()
        command.assert_not_called()

    def test_role_change_blocks_existing_panel_handlers(self):
        widget = self.populated()
        self.user.role = 'cajero'
        with patch('src.ui.central_view.CentralManager.request_price_change') as command:
            widget.request_price_change()
        command.assert_not_called()
        self.assertFalse(widget.isEnabled())

    def test_window_close_waits_for_central_worker_without_termination(self):
        central = Mock()
        central.is_running.return_value = True
        sync = Mock()
        sync.is_running.return_value = False
        updater = Mock()
        updater.isRunning.return_value = False
        window = SimpleNamespace(
            central_view=central, sync_controller=sync, updater_thread=updater,
            pos_view=SimpleNamespace(carrito=[]), _cart_close_confirmed=False,
            _close_requested=False, centralWidget=Mock(return_value=Mock()), lbl_sync=Mock(),
        )
        event = Mock()
        MainWindow.closeEvent(window, event)
        event.ignore.assert_called_once()
        event.accept.assert_not_called()
        self.assertTrue(window._close_requested)
        central.stop.assert_called_once()
        central.terminate.assert_not_called()


if __name__ == '__main__':
    unittest.main()
