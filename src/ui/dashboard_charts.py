"""Gráficos de administración sin dependencias adicionales ni datos de ejemplo."""
import math
from datetime import date

from PyQt6.QtCore import QRectF, QPointF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QFrame, QLabel, QToolTip, QVBoxLayout


COLORS = ('#0284C7', '#0F766E', '#C2410C', '#7C3AED', '#BE123C', '#475569')
TEXT = '#0F172A'
MUTED = '#475569'


def _number(value):
    if isinstance(value, bool):
        raise ValueError('Se requiere un número finito.')
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError('Se requiere un número finito.') from exc
    if not math.isfinite(result):
        raise ValueError('Se requiere un número finito.')
    return result


def _spanish(value, decimals=2):
    return f'{value:,.{decimals}f}'.replace(',', '_').replace('.', ',').replace('_', '.')


def format_money(value):
    return '$' + _spanish(_number(value))


def compact_money(value):
    value = _number(value)
    if abs(value) >= 1_000_000:
        return '$' + _spanish(value / 1_000_000, 1) + ' mill.'
    if abs(value) >= 1_000:
        return '$' + _spanish(value / 1_000, 1) + ' mil'
    return '$' + _spanish(value, 0)


def format_count(value):
    value = _number(value)
    return _spanish(value, 0 if value.is_integer() else 2)


def prepare_items(items, limit=6):
    """Valida antes de pintar; agrupa la cola sin perder valor ni inventar un ID."""
    prepared = []
    for index, item in enumerate(items):
        value = _number(item['value'])
        if value < 0:
            raise ValueError('Los valores de un gráfico no pueden ser negativos.')
        color = QColor(item.get('color') or COLORS[index % len(COLORS)])
        if not color.isValid():
            raise ValueError('Color inválido.')
        prepared.append(dict(label=str(item['label']), value=value,
                             color=color.name(), id=item.get('id')))
    try:
        total = math.fsum(item['value'] for item in prepared)
    except OverflowError as exc:
        raise ValueError('El total excede el rango permitido.') from exc
    if not math.isfinite(total):
        raise ValueError('El total excede el rango permitido.')
    prepared.sort(key=lambda item: item['value'], reverse=True)
    if len(prepared) > limit:
        tail = prepared[limit - 1:]
        prepared = prepared[:limit - 1] + [dict(
            label='Otros', value=math.fsum(item['value'] for item in tail),
            color=COLORS[-1], id=None)]
    return prepared, total


def percentages(items):
    total = math.fsum(item['value'] for item in items)
    if total == 0:
        return [0.0] * len(items)
    # Residuo solo en el último segmento positivo: el total siempre es 100.
    result = [max(0.0, min(100.0, item['value'] / total * 100)) for item in items]
    last = next(index for index in range(len(items) - 1, -1, -1) if items[index]['value'] > 0)
    result[last] = max(0.0, min(100.0, 100.0 - math.fsum(result[:last])))
    return result


class MetricCard(QFrame):
    def __init__(self, title, subtitle='', parent=None, accent='#0284C7'):
        super().__init__(parent)
        self.setObjectName('dashboardMetric')
        self.setStyleSheet('QFrame#dashboardMetric {background:white; border:1px solid #E2E8F0; border-radius:12px;}')
        self.setMinimumWidth(210)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        self.title = QLabel(title)
        self.title.setStyleSheet('color:#475569;font-size:13px;font-weight:600;background:transparent;')
        self.value = QLabel('—')
        color = QColor(accent)
        self.value.setStyleSheet(f'color:{color.name() if color.isValid() else COLORS[0]};font-size:27px;font-weight:700;background:transparent;')
        self.detail = QLabel(subtitle)
        self.detail.setWordWrap(True)
        self.detail.setStyleSheet('color:#475569;font-size:11px;background:transparent;')
        self.badge = QLabel('Datos anteriores')
        self.badge.setStyleSheet('color:#92400E;font-size:11px;background:#FEF3C7;border-radius:4px;padding:3px;')
        self.badge.hide()
        for label in (self.title, self.value, self.detail, self.badge):
            layout.addWidget(label)
        self.setAccessibleName(title)

    def set_value(self, text, detail=None):
        self.value.setText(str(text))
        if detail is not None:
            self.detail.setText(str(detail))
        self._update_description()

    def set_stale(self, stale):
        self.badge.setVisible(bool(stale))
        self._update_description()

    def _update_description(self):
        suffix = '. Datos anteriores' if not self.badge.isHidden() else ''
        self.setAccessibleDescription(f'{self.value.text()}. {self.detail.text()}{suffix}')


class _Chart(QFrame):
    def __init__(self, title='', subtitle='', parent=None):
        super().__init__(parent)
        self.title = title
        self.subtitle = subtitle
        self._stale = False
        self._available = True
        self._empty_text = 'Sin datos'
        self._summary = 'Sin datos'
        self._hits = []
        self.setMinimumSize(300, 340)
        self.setMouseTracking(True)
        self.setAccessibleName(title)

    def set_stale(self, stale):
        self._stale = bool(stale)
        self._description(self._summary)
        self.update()

    def _start(self):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor('#E2E8F0'), 1))
        painter.setBrush(QColor('white'))
        painter.drawRoundedRect(QRectF(0.5, 0.5, self.width()-1, self.height()-1), 12, 12)
        painter.setPen(QColor(TEXT))
        painter.setFont(QFont('Segoe UI', 11, QFont.Weight.DemiBold))
        title = painter.fontMetrics().elidedText(self.title, Qt.TextElideMode.ElideRight, self.width()-36)
        painter.drawText(QRectF(18, 13, self.width()-36, 25), Qt.AlignmentFlag.AlignLeft, title)
        painter.setFont(QFont('Segoe UI', 8))
        painter.setPen(QColor(MUTED))
        subtitle = painter.fontMetrics().elidedText(self.subtitle, Qt.TextElideMode.ElideRight, self.width()-36)
        painter.drawText(QRectF(18, 39, self.width()-36, 22), Qt.AlignmentFlag.AlignLeft, subtitle)
        if self._stale:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor('#FEF3C7'))
            painter.drawRoundedRect(QRectF(18, 62, 112, 20), 4, 4)
            painter.setPen(QColor('#92400E'))
            painter.drawText(QRectF(23, 62, 102, 20), Qt.AlignmentFlag.AlignVCenter, 'Datos anteriores')
        self._hits = []
        return painter

    def _empty(self, painter):
        painter.setPen(QColor(MUTED))
        painter.setFont(QFont('Segoe UI', 10))
        message = self._empty_text if self._available else 'Datos no disponibles'
        painter.drawText(QRectF(24, 100, self.width()-48, self.height()-130),
                         Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, message)

    def _description(self, values):
        self._summary = values
        suffix = '. Datos anteriores' if self._stale else ''
        self.setAccessibleDescription((values if self._available else 'Datos no disponibles') + suffix)

    def _item_at(self, position):
        for rect, tooltip, item in self._hits:
            if rect.contains(position):
                return tooltip, item
        return None

    def mouseMoveEvent(self, event):
        hit = self._item_at(event.position())
        if hit:
            QToolTip.showText(event.globalPosition().toPoint(), hit[0], self)
            self.setCursor(Qt.CursorShape.PointingHandCursor if hit[1].get('id') is not None else Qt.CursorShape.ArrowCursor)
        else:
            QToolTip.hideText()
            self.unsetCursor()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        QToolTip.hideText()
        self.unsetCursor()
        super().leaveEvent(event)


class DonutChart(_Chart):
    segment_clicked = pyqtSignal(object)

    def __init__(self, title='', subtitle='', parent=None):
        super().__init__(title, subtitle, parent)
        self.setMinimumHeight(410)
        self._items, self._total = [], 0
        self._center_text = None
        self._ring = QRectF()
        self._segments = []

    def set_data(self, items, center_text=None, empty_text='Sin datos', available=True):
        prepared, total = prepare_items(items)
        self._items, self._total = prepared, total
        self._available, self._empty_text = available, empty_text
        self._center_text = str(center_text) if center_text is not None else None
        self._description('; '.join(f"{item['label']}: {format_money(item['value'])} ({pct:.1f}%)"
                                   for item, pct in zip(prepared, percentages(prepared))) or empty_text)
        self._hits, self._segments = [], []
        self.update()

    def paintEvent(self, event):
        painter = self._start()
        self._segments = []
        if not self._available or not self._total:
            self._empty(painter)
            return
        size = min(150, self.width()-100)
        self._ring = QRectF((self.width()-size)/2, 89, size, size)
        start = 90.0
        for item, pct in zip(self._items, percentages(self._items)):
            span = pct * 3.6
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(item['color']))
            painter.drawPie(self._ring, round(start*16), -round(span*16))
            self._segments.append((90-start, 90-start+span, item, pct))
            start -= span
        painter.setBrush(QColor('white'))
        inner = self._ring.adjusted(size*.22, size*.22, -size*.22, -size*.22)
        painter.drawEllipse(inner)
        painter.setFont(QFont('Segoe UI', 9, QFont.Weight.DemiBold))
        painter.setPen(QColor(TEXT))
        center = self._center_text or compact_money(self._total)
        painter.drawText(inner, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, center)
        painter.setFont(QFont('Segoe UI', 8))
        for index, (item, pct) in enumerate(zip(self._items, percentages(self._items))):
            y = 254 + index*23
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(item['color']))
            painter.drawEllipse(QRectF(18, y+5, 9, 9))
            suffix = f"{compact_money(item['value'])} · {_spanish(pct, 1)}%"
            width = painter.fontMetrics().horizontalAdvance(suffix)+8
            label = painter.fontMetrics().elidedText(item['label'], Qt.TextElideMode.ElideRight,
                                                     max(20, self.width()-58-width))
            painter.setPen(QColor(TEXT))
            painter.drawText(QRectF(34, y, self.width()-52-width, 21), Qt.AlignmentFlag.AlignVCenter, label)
            painter.drawText(QRectF(self.width()-18-width, y, width, 21), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, suffix)
            tooltip = f"{item['label']}: {format_money(item['value'])} ({_spanish(pct, 1)}%)"
            self._hits.append((QRectF(14, y, self.width()-28, 22), tooltip, item))

    def _item_at(self, position):
        hit = super()._item_at(position)
        if hit:
            return hit
        if not self._available or not self._total or not self._segments:
            return None
        dx, dy = position.x()-self._ring.center().x(), position.y()-self._ring.center().y()
        radius = self._ring.width()/2
        if radius*.56 <= math.hypot(dx, dy) <= radius:
            angle = (math.degrees(math.atan2(dy, dx))+90) % 360
            for start, end, item, pct in self._segments:
                if start <= angle < end:
                    return f"{item['label']}: {format_money(item['value'])} ({_spanish(pct, 1)}%)", item
        return None

    def mousePressEvent(self, event):
        hit = self._item_at(event.position())
        if event.button() == Qt.MouseButton.LeftButton and hit and hit[1].get('id') is not None:
            self.segment_clicked.emit(hit[1]['id'])
        super().mousePressEvent(event)


class TrendChart(_Chart):
    def __init__(self, title='', subtitle='', parent=None):
        super().__init__(title, subtitle, parent)
        self._points = []
        self._granularity = 'day'

    def set_data(self, points, granularity='day', available=True, empty_text='Sin ventas en este período'):
        if granularity not in ('day', 'week', 'month', 'year'):
            raise ValueError('Agrupación temporal inválida.')
        prepared = []
        for point in points:
            stamp = date.fromisoformat(point['date'])
            total, count = _number(point['total']), _number(point['count'])
            if total < 0 or count < 0 or not count.is_integer():
                raise ValueError('Ventas y cantidades deben ser no negativas; cantidad entera.')
            prepared.append(dict(date=stamp, total=total, count=int(count)))
        prepared.sort(key=lambda item: item['date'])
        if len({point['date'] for point in prepared}) != len(prepared):
            raise ValueError('Los períodos no pueden repetirse.')
        self._points, self._granularity = prepared, granularity
        self._available, self._empty_text = available, empty_text
        self._description('; '.join(f"{p['date'].strftime('%d/%m/%Y')}: {format_money(p['total'])}, {p['count']} ventas"
                                   for p in prepared) or empty_text)
        self._hits = []
        self.update()

    def paintEvent(self, event):
        painter = self._start()
        if not self._available or not self._points or not any(p['total'] > 0 or p['count'] > 0 for p in self._points):
            self._empty(painter)
            return
        maximum = max(p['total'] for p in self._points) or 1
        painter.setFont(QFont('Segoe UI', 8))
        left = max(64, painter.fontMetrics().horizontalAdvance(compact_money(maximum))+22)
        plot = QRectF(left, 102, max(70, self.width()-left-24), max(90, self.height()-152))
        for tick in range(5):
            y = plot.bottom()-plot.height()*tick/4
            painter.setPen(QPen(QColor('#E2E8F0'), 1))
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            painter.setPen(QColor(MUTED))
            painter.drawText(QRectF(4, y-10, left-12, 20), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                             compact_money(maximum*tick/4))
        first, last = self._points[0]['date'], self._points[-1]['date']
        days = (last-first).days
        coords = [QPointF(plot.left() + ((p['date']-first).days/days if days else .5)*plot.width(),
                          plot.bottom()-(p['total']/maximum)*plot.height()) for p in self._points]
        path = QPainterPath(coords[0])
        for point in coords[1:]:
            path.lineTo(point)
        if len(coords) > 1:
            fill = QPainterPath(path)
            fill.lineTo(coords[-1].x(), plot.bottom())
            fill.lineTo(coords[0].x(), plot.bottom())
            fill.closeSubpath()
            painter.fillPath(fill, QColor('#E0F2FE'))
        painter.setPen(QPen(QColor(COLORS[0]), 2))
        # drawPath también rellena trazados abiertos: no permitir que el pincel
        # blanco del fondo tape el área de picos y valles ya pintada.
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
        for index, (point, original) in enumerate(zip(coords, self._points)):
            painter.setBrush(QColor(COLORS[0]))
            painter.drawEllipse(point, 3.5, 3.5)
            stamp = original['date']
            label = stamp.strftime('%Y' if self._granularity == 'year' else '%m/%Y' if self._granularity == 'month' else '%d/%m')
            if self._granularity == 'week':
                label = 'Sem. ' + label
            # Etiquetas espaciadas: siempre primera y última, como máximo tres.
            label_indices = {0, len(coords)-1}
            if len(coords) > 2 and plot.width() >= 240:
                label_indices.add(len(coords)//2)
            if index in label_indices:
                painter.setPen(QColor(MUTED))
                x = max(plot.left()-20, min(point.x()-36, self.width()-82))
                painter.drawText(QRectF(x, plot.bottom()+10, 76, 24), Qt.AlignmentFlag.AlignCenter, label)
                painter.setPen(QPen(QColor(COLORS[0]), 2))
            self._hits.append((QRectF(point.x()-12, point.y()-12, 24, 24),
                               f"{stamp.strftime('%d/%m/%Y')}: {format_money(original['total'])} · {format_count(original['count'])} ventas", {}))


class BarChart(_Chart):
    bar_clicked = pyqtSignal(object)

    def __init__(self, title='', subtitle='', parent=None):
        super().__init__(title, subtitle, parent)
        self._items, self._total = [], 0
        self._unit = 'productos'

    def set_data(self, items, unit='productos', available=True, empty_text='Sin datos'):
        prepared, total = prepare_items(items, limit=9)
        self._items, self._total = prepared, total
        self._unit, self._available, self._empty_text = str(unit), available, empty_text
        self.setMinimumHeight(max(340, 110+len(prepared)*42))
        self._description('; '.join(f"{item['label']}: {format_count(item['value'])} {self._unit}" for item in prepared) or empty_text)
        self._hits = []
        self.update()

    def paintEvent(self, event):
        painter = self._start()
        if not self._available or not self._items or not self._total:
            self._empty(painter)
            return
        maximum = max(item['value'] for item in self._items)
        painter.setFont(QFont('Segoe UI', 8))
        for index, item in enumerate(self._items):
            y = 94+index*42
            value = format_count(item['value'])
            value_width = painter.fontMetrics().horizontalAdvance(value)+12
            label = painter.fontMetrics().elidedText(item['label'], Qt.TextElideMode.ElideRight,
                                                     max(30, self.width()-48-value_width))
            painter.setPen(QColor(TEXT))
            painter.drawText(QRectF(18, y, self.width()-36-value_width, 19), Qt.AlignmentFlag.AlignVCenter, label)
            painter.drawText(QRectF(self.width()-18-value_width, y, value_width, 19), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, value)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor('#F1F5F9'))
            painter.drawRoundedRect(QRectF(18, y+23, self.width()-36, 9), 4, 4)
            painter.setBrush(QColor(item['color']))
            painter.drawRoundedRect(QRectF(18, y+23, (self.width()-36)*(item['value']/maximum), 9), 4, 4)
            self._hits.append((QRectF(14, y, self.width()-28, 36),
                               f"{item['label']}: {value} {self._unit}", item))

    def mousePressEvent(self, event):
        hit = self._item_at(event.position())
        if event.button() == Qt.MouseButton.LeftButton and hit and hit[1].get('id') is not None:
            self.bar_clicked.emit(hit[1]['id'])
        super().mousePressEvent(event)
