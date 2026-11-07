import math
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QImage
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from src.ui.dashboard_charts import (
    MetricCard, DonutChart, TrendChart, BarChart, compact_money,
    format_money, format_count, prepare_items, percentages,
)


class ChartHelpers(unittest.TestCase):
    def test_spanish_numbers_and_compact_units(self):
        self.assertEqual(format_money(1234.56), '$1.234,56')
        self.assertEqual(format_money(-12.5), '$-12,50')
        self.assertEqual(compact_money(1250000), '$1,2 mill.')
        self.assertEqual(compact_money(12500), '$12,5 mil')
        self.assertEqual(format_count(1234), '1.234')

    def test_grouping_conserves_sum_and_does_not_assign_other_branch(self):
        items, total = prepare_items([dict(label=f'Sucursal {i}', value=i, id=i) for i in range(12)])
        self.assertEqual(len(items), 6)
        self.assertEqual(total, 66)
        self.assertEqual(math.fsum(i['value'] for i in items), total)
        self.assertEqual(items[0]['id'], 11)
        self.assertEqual(items[-1]['label'], 'Otros')
        self.assertIsNone(items[-1]['id'])

    def test_percentages_conserve_hundred_and_zero_has_no_fake_share(self):
        items, _ = prepare_items([dict(label=str(i), value=1) for i in range(3)])
        self.assertAlmostEqual(math.fsum(percentages(items)), 100)
        self.assertTrue(all(0 <= n <= 100 for n in percentages(items)))
        self.assertEqual(percentages([dict(value=0), dict(value=0)]), [0, 0])
        self.assertEqual(percentages([]), [])

    def test_rejects_nonfinite_negative_and_overflow_totals(self):
        for value in (-1, float('nan'), float('inf'), float('-inf'), True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                prepare_items([dict(label='Inválido', value=value)])
        with self.assertRaises(ValueError):
            prepare_items([dict(label='Grande', value=1e308)]*2)


class ChartRendering(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def render_chart(self, widget, width, height):
        widget.resize(width, height)
        widget.show()
        self.app.processEvents()
        image = QImage(widget.size(), QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        widget.render(image)
        self.assertFalse(image.isNull())
        self.assertGreater(image.pixelColor(widget.width()//2, widget.height()//2).alpha(), 0)
        self.assertTrue(widget.accessibleName())
        widget.hide()
        return image

    def test_all_widgets_empty_unavailable_zero_small_and_large(self):
        for cls in (DonutChart, TrendChart, BarChart):
            widget = cls('Resumen', 'Contexto de los datos')
            try:
                for width in (300, 760):
                    for available in (True, False):
                        widget.set_data([], available=available)
                        self.render_chart(widget, width, 420)
                values = [dict(date='2026-01-01', total=0, count=0)] if cls is TrendChart else [dict(label='Cero', value=0)]
                widget.set_data(values)
                widget.set_stale(True)
                self.render_chart(widget, 300, 420)
                self.assertFalse(widget._hits)
            finally:
                widget.close()

    def test_metric_card_preserves_value_and_displays_stale_badge(self):
        card = MetricCard('Ventas', 'Período seleccionado')
        card.set_value('$1.234,56', '10 ventas')
        card.set_stale(True)
        self.render_chart(card, 300, 180)
        self.assertEqual(card.value.text(), '$1.234,56')
        self.assertFalse(card.badge.isHidden())
        self.assertIn('10 ventas', card.accessibleDescription())
        card.close()

    def test_donut_legend_click_selects_real_branch_and_others_cannot_select(self):
        chart = DonutChart('Ventas por sucursal')
        received = []
        chart.segment_clicked.connect(received.append)
        chart.set_data([dict(label=f'Sucursal {i}', value=i+1, id=f'id-{i}') for i in range(9)])
        self.render_chart(chart, 300, 420)
        chart.show()
        self.app.processEvents()
        first = chart._hits[0][0].center().toPoint()
        QTest.mouseClick(chart, Qt.MouseButton.LeftButton, pos=first)
        self.assertEqual(received, ['id-8'])
        QTest.mouseClick(chart, Qt.MouseButton.LeftButton, pos=chart._hits[-1][0].center().toPoint())
        self.assertEqual(received, ['id-8'])
        chart.close()

    def test_bars_ties_many_branches_and_click(self):
        chart = BarChart('Stock por sucursal')
        received = []
        chart.bar_clicked.connect(received.append)
        chart.set_data([dict(label='Nombre de sucursal muy largo '+str(i), value=100, id=i) for i in range(12)])
        self.render_chart(chart, 300, 340)
        self.assertEqual(len(chart._items), 9)
        self.assertEqual(math.fsum(i['value'] for i in chart._items), 1200)
        self.assertLess(chart._hits[-1][0].bottom(), chart.height())
        chart.show()
        self.app.processEvents()
        QTest.mouseClick(chart, Qt.MouseButton.LeftButton, pos=chart._hits[0][0].center().toPoint())
        self.assertEqual(received, [0])
        chart.close()

    def test_trend_single_point_and_all_granularities(self):
        chart = TrendChart('Evolución de ventas')
        try:
            for granularity in ('day', 'week', 'month', 'year'):
                chart.set_data([dict(date='2026-01-01', total=100, count=2)], granularity=granularity)
                self.render_chart(chart, 300, 340)
                self.assertEqual(len(chart._hits), 1)
                self.assertIn('$100,00', chart._hits[0][1])
            chart.set_data([dict(date=f'2026-01-{i:02}', total=i*1000, count=i) for i in range(1, 25)])
            self.render_chart(chart, 760, 420)
            self.assertEqual(len(chart._hits), 24)
        finally:
            chart.close()

    def test_trend_invalid_numbers_dates_and_duplicate_buckets(self):
        chart = TrendChart('Ventas')
        for field, value in (('total', -1), ('total', float('nan')), ('count', 1.5), ('count', -1), ('date', 'incorrecta')):
            point = dict(date='2026-01-01', total=100, count=1)
            point[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                chart.set_data([point])
        with self.assertRaises(ValueError):
            chart.set_data([dict(date='2026-01-01', total=100, count=1)]*2)
        chart.close()

    def test_trend_area_follows_peaks_and_valleys_without_white_polygon(self):
        chart = TrendChart('Evolución')
        try:
            chart.set_data([dict(date=f'2026-01-{index+1:02}', total=value, count=1)
                            for index, value in enumerate((10, 30, 10, 30, 10))])
            for width in (300, 760):
                image = self.render_chart(chart, width, 420)
                peak = chart._hits[1][0].center()
                valley = chart._hits[2][0].center()
                # El área bajo cada pico es azul, aun por encima de la recta
                # entre el primero y último punto. Encima del valle queda blanco.
                self.assertEqual(image.pixelColor(round(peak.x()), round(peak.y()+35)).name(), '#e0f2fe')
                self.assertEqual(image.pixelColor(round(valley.x()), round(valley.y()-35)).name(), '#ffffff')
                self.assertEqual(image.pixelColor(round(valley.x()), round(valley.y()+25)).name(), '#e0f2fe')
        finally:
            chart.close()


if __name__ == '__main__':
    unittest.main()
