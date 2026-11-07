import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from types import SimpleNamespace
import unittest
from unittest.mock import patch
from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import QApplication
from src.ui.central_view import CentralView, _money


class VisualDashboardUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.user = SimpleNamespace(user_id='admin', role='admin')
        for name in ('require_user', 'current_user'):
            p = patch('src.ui.central_view.AuthManager.' + name, return_value=self.user)
            p.start()
            self.addCleanup(p.stop)
        self.view = CentralView()
        self.addCleanup(self.view.deleteLater)
        self.dashboard = {
            'totals': {'total_vendido': 120000, 'ventas_count': 20, 'alertas_stock': 8},
            'branches': [
                {'id': 'one', 'nombre': 'Simoca', 'total_vendido': 90000, 'alertas_stock': 5, 'pendientes': 3},
                {'id': 'two', 'nombre': 'Otra sucursal', 'total_vendido': 30000, 'alertas_stock': 3, 'pendientes': None},
            ],
            'charts': {
                'sales_trend': {'granularity': 'week', 'points': [{'date': '2026-11-01', 'total': 120000, 'count': 20}]},
                'payment_methods': [{'label': 'MIXTO', 'total': 120000, 'count': 20}],
                'cash_closures': {'balanced_count': 3, 'shortage_count': 2, 'surplus_count': 1, 'shortage_total': 150, 'surplus_total': 80},
            },
            'fetched_at': '2026-11-06T16:00:00Z',
        }

    def result(self):
        self.view._show_result({'dashboard': self.dashboard, 'page': {'rows': [{'total': 1}], 'has_more': False}}, 'ventas')

    def test_overview_is_default_and_money_is_argentine(self):
        self.assertEqual(self.view.sections.currentIndex(), 0)
        self.assertEqual(_money(1234.56), '$1.234,56')
        self.assertEqual(_money(None), '—')

    def test_metrics_and_charts_use_complete_server_data_not_page_rows(self):
        with patch.object(self.view.cards['sales'], 'set_value') as sales, \
                patch.object(self.view.cards['average'], 'set_value') as average, \
                patch.object(self.view.cards['cash'], 'set_value') as cash, \
                patch.object(self.view.cards['pending'], 'set_value') as pending, \
                patch.object(self.view.trend_chart, 'set_data') as trend, \
                patch.object(self.view.payment_chart, 'set_data') as payments:
            self.result()
        sales.assert_called_once_with('$120.000,00')
        average.assert_called_once_with('$6.000,00', 'Total vendido / operaciones')
        cash.assert_called_once_with('3', '2 con faltante · 1 con sobrante')
        pending.assert_called_once_with('3', '1 sucursales sin informe')
        self.assertEqual(trend.call_args.args[0][0]['total'], 120000)
        self.assertEqual(trend.call_args.kwargs['granularity'], 'week')
        self.assertEqual(payments.call_args.args[0][0]['label'], 'MIXTO')
        self.assertIn('$150,00', self.view.cash_detail.text())
        self.assertIn('$80,00', self.view.cash_detail.text())

    def test_missing_migration_shows_unavailable_instead_of_zero_or_page_graph(self):
        self.dashboard.pop('charts')
        with patch.object(self.view.trend_chart, 'set_data') as trend, \
                patch.object(self.view.payment_chart, 'set_data') as payments, \
                patch.object(self.view.cards['cash'], 'set_value') as cash:
            self.result()
        self.assertFalse(trend.call_args.kwargs['available'])
        self.assertFalse(payments.call_args.kwargs['available'])
        cash.assert_called_once_with('—', 'Sin información gráfica de arqueos')
        self.assertIn('actualizar la configuración', self.view.charts_notice.text())

    def test_zero_sales_have_no_invented_average(self):
        self.dashboard['totals'].update(total_vendido=0, ventas_count=0)
        with patch.object(self.view.cards['average'], 'set_value') as average:
            self.result()
        average.assert_called_once_with('—', 'Sin operaciones')

    def test_free_sales_and_absent_inventory_are_not_reported_as_no_operations_or_healthy_stock(self):
        self.dashboard['totals'].update(total_vendido=0, ventas_count=20)
        with patch.object(self.view.branch_chart, 'set_data') as branches, \
                patch.object(self.view.stock_chart, 'set_data') as stock, \
                patch.object(self.view.cards['average'], 'set_value') as average:
            self.result()
        self.assertEqual(branches.call_args.kwargs['empty_text'], 'Sin importe para distribuir')
        self.assertEqual(stock.call_args.kwargs['empty_text'], 'Sin inventario recibido')
        average.assert_called_once_with('$0,00', 'Total vendido / operaciones')

    def test_filter_change_marks_every_visible_metric_and_chart_stale(self):
        self.result()
        widgets = list(self.view.cards.values()) + [self.view.trend_chart, self.view.branch_chart, self.view.payment_chart, self.view.stock_chart, self.view.cash_chart]
        patches = [patch.object(widget, 'set_stale') for widget in widgets]
        mocks = [p.start() for p in patches]
        try:
            self.view.filters_changed()
            for mock in mocks:
                mock.assert_called_once_with(True)
        finally:
            for p in patches:
                p.stop()
        self.assertFalse(self.view.valid_snapshot)
        self.assertIn('Datos anteriores', self.view.cash_detail.text())

    def test_presets_change_dates_once_and_make_one_query(self):
        today = QDate.currentDate()
        for key, expected in (('today', today), ('week', today.addDays(-6)), ('month', QDate(today.year(), today.month(), 1)), ('30days', today.addDays(-29))):
            with self.subTest(key=key), patch.object(self.view, 'filters_changed') as changed, patch.object(self.view, 'refresh') as refresh:
                self.view.set_period(key)
                self.assertEqual(self.view.date_from.date(), expected)
                self.assertEqual(self.view.date_to.date(), today)
                changed.assert_called_once()
                refresh.assert_called_once()

    def test_branch_chart_drilldown_selects_id_and_keeps_filters(self):
        self.result()
        original = (self.view.date_from.date(), self.view.date_to.date())
        with patch.object(self.view, 'refresh') as refresh:
            self.view.select_branch({'id': 'two'})
            refresh.assert_called_once()
        self.assertEqual(self.view.branch.currentData(), 'two')
        self.assertEqual((self.view.date_from.date(), self.view.date_to.date()), original)
        with patch.object(self.view, 'refresh') as refresh:
            self.view.select_branch({'id': None})
            refresh.assert_not_called()

    def test_detail_link_changes_section_and_corresponding_table(self):
        with patch.object(self.view, 'refresh'):
            self.view.show_detail('cierres')
        self.assertEqual(self.view.sections.currentIndex(), 1)
        self.assertEqual(self.view._kind(), 'cierres')

    def test_resizing_overview_stacks_charts_without_overlap_or_horizontal_overflow(self):
        self.result()
        self.view.resize(1440, 1100)
        self.view.show()
        self.app.processEvents()
        self.assertGreater(self.view.branch_chart.x(), self.view.trend_chart.x())
        self.view.resize(760, 1100)
        for _ in range(4):
            self.app.processEvents()
        self.assertGreater(self.view.branch_chart.y(), self.view.trend_chart.geometry().bottom())
        self.assertLessEqual(self.view.overview.widget().width(), self.view.overview.viewport().width())
        self.view.close()


if __name__ == '__main__':
    unittest.main()
