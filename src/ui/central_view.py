"""Consulta central de sucursales y solicitudes de precios, reservada a administración."""
import math
from datetime import datetime

from PyQt6.QtCore import QDate, QThread, QTimer, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QDateEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QTabWidget,
    QMessageBox, QInputDialog, QGridLayout, QScrollArea, QSizePolicy, QLayout,
)

from src.core.auth_manager import AuthManager
from src.core.central_manager import CentralManager
from src.ui.dashboard_charts import MetricCard, DonutChart, TrendChart, BarChart


def _admin():
    user = AuthManager.require_user()
    if user.role != 'admin':
        raise PermissionError('La administración central requiere una cuenta administradora.')
    return user


def _money(value):
    return '—' if value is None else ("$" + f"{float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))


def _time(value):
    if not value:
        return 'Sin datos recibidos'
    try:
        stamp = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return stamp.astimezone().strftime('%d/%m/%Y %H:%M')
    except (TypeError, ValueError):
        return str(value)


class CentralWorker(QThread):
    def __init__(self, action, params, generation, user_id, parent=None):
        super().__init__(parent)
        self.action = action
        self.params = params
        self.generation = generation
        self.user_id = user_id
        self.result = None
        self.error = None

    def run(self):
        try:
            user = _admin()
            if user.user_id != self.user_id:
                raise PermissionError('La sesión cambió. Vuelva a consultar.')
            if self.action == 'price':
                self.result = CentralManager.request_price_change(**self.params)
            else:
                filters = {k: self.params[k] for k in ('branch_id', 'fecha_desde', 'fecha_hasta')}
                dashboard = CentralManager.fetch_dashboard(**filters)
                page = CentralManager.fetch_page(
                    self.params['kind'], **filters, page=self.params['page'], page_size=100,
                )
                self.result = {'dashboard': dashboard, 'page': page}
        except Exception as exc:
            self.error = str(exc)


class CentralView(QWidget):
    idle = pyqtSignal()
    KINDS = ('productos', 'ventas', 'cierres', 'comandos')
    COLUMNS = {
        'productos': (
            ('Sucursal', 'sucursal_nombre'), ('Código', 'codigo_barras'), ('Producto', 'nombre'),
            ('Stock', 'stock_actual'), ('Mínimo', 'stock_minimo'), ('Contado', 'precio_contado'),
            ('Tarjeta', 'precio_tarjeta'), ('Revisión de precios', 'catalog_revision'),
        ),
        'ventas': (
            ('Sucursal', 'sucursal_nombre'), ('Venta local', 'local_id'), ('Fecha', 'fecha'),
            ('Cliente', 'cliente_nombre'), ('Medio de pago', 'metodo_pago'), ('Total', 'total'),
            ('Vendedor registrado', 'responsable_nombre'),
        ),
        'cierres': (
            ('Sucursal', 'sucursal_nombre'), ('Fecha de cierre', 'fecha_cierre'),
            ('Responsable', 'responsable_nombre'), ('Usuario de cierre', 'cierre_usuario_nombre'),
            ('Esperado', 'monto_esperado'), ('Contado', 'monto_cierre'), ('Diferencia', 'diferencia'),
        ),
        'comandos': (
            ('Sucursal', 'sucursal_nombre'), ('Solicitud', 'id'), ('Fecha', 'creado_en'),
            ('Producto', 'producto_id'), ('Contado solicitado', 'precio_contado'),
            ('Tarjeta solicitada', 'precio_tarjeta'), ('Estado', 'estado'), ('Resultado', 'detalle'),
        ),
    }
    MONEY_KEYS = {'precio_contado', 'precio_tarjeta', 'total', 'monto_esperado', 'monto_cierre', 'diferencia'}

    def __init__(self, parent=None):
        _admin()
        super().__init__(parent)
        self.worker = None
        self.stopped = False
        self.generation = 0
        self.page = 0
        self.has_more = False
        self.loaded = False
        self.valid_snapshot = False
        self.branch_names = {}
        self.rows = {kind: [] for kind in self.KINDS}
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        title = QLabel('Resumen del negocio')
        title.setStyleSheet('font-size: 25px; font-weight: bold; color: #0F172A;')
        layout.addWidget(title)
        info = QLabel('Administración central · Ventas recibidas y estado de cada sucursal. Los locales sin conexión pueden tener operaciones pendientes.')
        info.setWordWrap(True)
        info.setStyleSheet('color: #64748B;')
        layout.addWidget(info)
        branch_row = QHBoxLayout()
        branch_row.addWidget(QLabel('Sucursal'))
        self.branch = QComboBox()
        self.branch.addItem('Todas las sucursales', None)
        self.branch.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        branch_row.addWidget(self.branch, 1)
        self.refresh_button = QPushButton('Actualizar')
        self.refresh_button.clicked.connect(self.refresh)
        branch_row.addWidget(self.refresh_button)
        layout.addLayout(branch_row)
        presets = QHBoxLayout()
        self.period_buttons = {}
        for key, label in (('today', 'Hoy'), ('week', '7 días'), ('month', 'Este mes'), ('30days', '30 días')):
            button = QPushButton(label)
            button.clicked.connect(lambda checked=False, key=key: self.set_period(key))
            self.period_buttons[key] = button
            presets.addWidget(button)
        presets.addStretch()
        layout.addLayout(presets)
        dates = QHBoxLayout()
        dates.addWidget(QLabel('Desde'))
        self.date_from = QDateEdit(QDate.currentDate().addDays(-29))
        self.date_to = QDateEdit(QDate.currentDate())
        for date in (self.date_from, self.date_to):
            date.setCalendarPopup(True)
            date.setDisplayFormat('dd/MM/yyyy')
        dates.addWidget(self.date_from)
        dates.addWidget(QLabel('Hasta'))
        dates.addWidget(self.date_to)
        dates.addStretch()
        layout.addLayout(dates)
        self.branch.currentIndexChanged.connect(self.filters_changed)
        self.date_from.dateChanged.connect(self.filters_changed)
        self.date_to.dateChanged.connect(self.filters_changed)
        self.status = QLabel('Pulse Actualizar para consultar. No es una vista en tiempo real.')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.summary = QLabel()
        self.summary.hide()  # Compatibilidad con integraciones del resumen textual.
        self.sections = QTabWidget()
        layout.addWidget(self.sections, 1)
        self.overview = QScrollArea()
        self.overview.setWidgetResizable(True)
        self.overview.setFrameShape(QScrollArea.Shape.NoFrame)
        overview_content = QWidget()
        overview_layout = QVBoxLayout(overview_content)
        overview_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinAndMaxSize)
        overview_layout.setContentsMargins(0, 12, 0, 8)
        self.cards_grid = QGridLayout()
        overview_layout.addLayout(self.cards_grid)
        self.cards = {}
        card_specs = (
            ('sales', 'Ventas del período', 'Ventas registradas; no equivale a cobros', 'ventas'),
            ('operations', 'Operaciones', 'Ventas recibidas para el período', 'ventas'),
            ('average', 'Ticket promedio', 'Total vendido / operaciones', 'ventas'),
            ('stock', 'Productos con stock bajo', 'Estado actual recibido; no filtra por fecha', 'productos'),
            ('cash', 'Cajas con diferencia', 'Faltantes y sobrantes del período', 'cierres'),
            ('pending', 'Pendientes informados', 'Último reporte de las sucursales', None),
        )
        self.card_widgets = []
        for key, label, subtitle, kind in card_specs:
            container = QWidget()
            box = QVBoxLayout(container)
            box.setContentsMargins(0, 0, 0, 0)
            card = MetricCard(label, subtitle)
            card.set_value('—')
            self.cards[key] = card
            box.addWidget(card)
            link = QPushButton('Ver estado de sucursales' if kind is None else 'Ver detalle')
            link.clicked.connect(lambda checked=False, kind=kind: self.show_detail(kind))
            box.addWidget(link)
            self.card_widgets.append(container)
        self.charts_grid = QGridLayout()
        overview_layout.addLayout(self.charts_grid)
        self.trend_chart = TrendChart('Evolución de ventas', 'Ventas del período, agrupadas por fecha')
        self.branch_chart = DonutChart('Ventas por sucursal', 'Participación en el total vendido · pulse para consultar el local')
        self.payment_chart = DonutChart('Medios de pago', 'Mixto: venta combinada sin desglose · importes de ventas, no cobros')
        self.stock_chart = BarChart('Alertas de stock por sucursal', 'Estado actual recibido · pulse para consultar el local')
        self.cash_chart = BarChart('Arqueos de caja', 'Cantidad de cierres del período, según su diferencia')
        self.cash_detail = QLabel('Faltantes: — · Sobrantes: —')
        self.cash_detail.setWordWrap(True)
        self.cash_panel = QWidget()
        cash_layout = QVBoxLayout(self.cash_panel)
        cash_layout.setContentsMargins(0, 0, 0, 0)
        cash_layout.addWidget(self.cash_chart)
        cash_layout.addWidget(self.cash_detail)
        self.chart_widgets = [self.trend_chart, self.branch_chart, self.payment_chart, self.stock_chart, self.cash_panel]
        self.branch_chart.segment_clicked.connect(self.select_branch)
        self.stock_chart.bar_clicked.connect(self.select_branch)
        self.charts_notice = QLabel('Los gráficos se completan al consultar. Stock y pendientes corresponden al último reporte recibido.')
        self.charts_notice.setWordWrap(True)
        overview_layout.addWidget(self.charts_notice)
        overview_layout.addStretch()
        self.overview.setWidget(overview_content)
        self.sections.addTab(self.overview, 'Resumen visual')
        detail = QWidget()
        detail_layout = QVBoxLayout(detail)
        detail_layout.setContentsMargins(0, 10, 0, 0)
        detail_info = QLabel('Estado de sucursales · Última recepción y pendientes informados. Las fechas filtran ventas, cierres y solicitudes; stock muestra el estado actual recibido.')
        detail_info.setWordWrap(True)
        detail_layout.addWidget(detail_info)
        self.branches_table = self._table([
            'Sucursal', 'Última recepción', 'Operaciones pendientes', 'Total vendido', 'Ventas', 'Productos', 'Alertas stock', 'Cierres', 'Diferencias',
        ])
        self.branches_table.setMaximumHeight(190)
        detail_layout.addWidget(self.branches_table)
        self.tabs = QTabWidget()
        self.tables = {}
        for kind, label in zip(self.KINDS, ('Productos y stock', 'Ventas', 'Cierres de caja', 'Cambios de precios')):
            table = self._table([title for title, _ in self.COLUMNS[kind]])
            self.tables[kind] = table
            self.tabs.addTab(table, label)
        self.tabs.currentChanged.connect(self.tab_changed)
        self.tables['productos'].itemSelectionChanged.connect(self._update_buttons)
        detail_layout.addWidget(self.tabs, 1)
        actions = QVBoxLayout()
        self.price_button = QPushButton('Solicitar cambio de precios')
        self.price_button.setEnabled(False)
        self.price_button.clicked.connect(self.request_price_change)
        actions.addWidget(self.price_button)
        paging = QHBoxLayout()
        self.previous_button = QPushButton('Anterior')
        self.next_button = QPushButton('Siguiente')
        self.page_label = QLabel('Página 1 · hasta 100 registros')
        self.page_label.setWordWrap(True)
        self.previous_button.clicked.connect(lambda: self.change_page(-1))
        self.next_button.clicked.connect(lambda: self.change_page(1))
        paging.addWidget(self.previous_button)
        paging.addWidget(self.page_label, 1)
        paging.addWidget(self.next_button)
        actions.addLayout(paging)
        detail_layout.addLayout(actions)
        self.sections.addTab(detail, 'Detalle de operaciones')
        self._layout_overview()
        self._mark_stale()
        self._update_buttons()

    def _layout_overview(self):
        card_columns = 3 if self.width() >= 1000 else 2
        chart_columns = 2 if self.width() >= 1000 else 1
        for grid, widgets, columns in ((self.cards_grid, self.card_widgets, card_columns), (self.charts_grid, self.chart_widgets, chart_columns)):
            for widget in widgets:
                grid.removeWidget(widget)
            for index, widget in enumerate(widgets):
                grid.addWidget(widget, index // columns, index % columns)
            for col in range(3):
                grid.setColumnStretch(col, 1 if col < columns else 0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'cards_grid'):
            self._layout_overview()

    def _mark_stale(self):
        for widget in list(self.cards.values()) + [self.trend_chart, self.branch_chart, self.payment_chart, self.stock_chart, self.cash_chart]:
            widget.set_stale(True)
        self.cash_detail.setText('Datos anteriores · Faltantes y sobrantes sin actualizar')

    def set_period(self, key):
        if self.is_running() or self.stopped or not self._authorized():
            return
        today = QDate.currentDate()
        start = {'today': today, 'week': today.addDays(-6), 'month': QDate(today.year(), today.month(), 1), '30days': today.addDays(-29)}[key]
        for control, value in ((self.date_from, start), (self.date_to, today)):
            control.blockSignals(True)
            control.setDate(value)
            control.blockSignals(False)
        self.filters_changed()
        self.refresh()

    def select_branch(self, item):
        branch_id = item.get('id') if isinstance(item, dict) else item
        if branch_id is None or self.stopped or self.is_running() or not self.valid_snapshot or not self._authorized():
            return
        index = self.branch.findData(branch_id)
        if index < 0:
            return
        if self.branch.currentIndex() == index:
            self.filters_changed()
        else:
            self.branch.setCurrentIndex(index)
        self.refresh()

    def show_detail(self, kind=None):
        if self.stopped or not self._authorized():
            return
        self.sections.setCurrentIndex(1)
        if kind is not None:
            self.tabs.setCurrentIndex(self.KINDS.index(kind))

    def _show_visuals(self, dashboard):
        totals = dashboard.get('totals', {})
        branches = dashboard.get('branches', [])
        charts = dashboard.get('charts') or {}
        total = totals.get('total_vendido')
        count = totals.get('ventas_count')
        self.cards['sales'].set_value(_money(total))
        self.cards['operations'].set_value('—' if count is None else str(count))
        self.cards['average'].set_value(_money(total / count) if total is not None and count else '—',
                                        'Sin operaciones' if count == 0 else 'Total vendido / operaciones')
        stock = totals.get('alertas_stock')
        self.cards['stock'].set_value('—' if stock is None else str(stock))
        known = [row['pendientes'] for row in branches if row.get('pendientes') is not None]
        missing = len(branches) - len(known)
        self.cards['pending'].set_value(str(sum(known)) if known else '—',
                                        f'{missing} sucursales sin informe' if missing else 'Último reporte; no es tiempo real')
        colors = ['#0284C7', '#10B981', '#8B5CF6', '#F59E0B', '#EC4899', '#14B8A6']
        branch_sales = [{'label': row['nombre'], 'value': row.get('total_vendido', 0), 'id': row['id'],
                         'color': colors[index % len(colors)]} for index, row in enumerate(branches)]
        branch_stock = [{'label': row['nombre'], 'value': row.get('alertas_stock', 0), 'id': row['id'],
                         'color': '#F59E0B'} for row in branches if row.get('productos_count', 0) > 0]
        self.branch_chart.set_data(branch_sales, center_text=_money(total), empty_text='Sin importe para distribuir')
        self.stock_chart.set_data(branch_stock, unit='productos', empty_text='Sin productos bajo mínimo' if branch_stock else 'Sin inventario recibido')
        trend = charts.get('sales_trend')
        self.trend_chart.set_data(trend.get('points', []) if trend else [],
                                  granularity=trend.get('granularity', 'day') if trend else 'day',
                                  available=trend is not None,
                                  empty_text='Sin importe de ventas en el período' if trend is not None else 'Actualizar configuración de reportes')
        payments = charts.get('payment_methods')
        self.payment_chart.set_data([
            {'label': row['label'], 'value': row['total'], 'color': colors[index % len(colors)]}
            for index, row in enumerate(payments or [])
        ], available=payments is not None,
            empty_text='Sin importe para distribuir' if payments is not None else 'Actualizar configuración de reportes')
        cash = charts.get('cash_closures')
        if cash is not None:
            shortage = cash['shortage_count']
            surplus = cash['surplus_count']
            self.cards['cash'].set_value(str(shortage + surplus), f'{shortage} con faltante · {surplus} con sobrante')
            self.cash_chart.set_data([
                {'label': 'Sin diferencia', 'value': cash['balanced_count'], 'color': '#10B981'},
                {'label': 'Con faltante', 'value': shortage, 'color': '#EF4444'},
                {'label': 'Con sobrante', 'value': surplus, 'color': '#F59E0B'},
            ], unit='cierres', empty_text='Sin cierres en el período')
            self.cash_detail.setText(f"Faltantes: {_money(cash['shortage_total'])} · Sobrantes: {_money(cash['surplus_total'])}\nLos montos se muestran separados; no se compensan.")
        else:
            self.cards['cash'].set_value('—', 'Sin información gráfica de arqueos')
            self.cash_chart.set_data([], unit='cierres', available=False, empty_text='Actualizar configuración de reportes')
            self.cash_detail.setText('Faltantes: — · Sobrantes: — · Sin información gráfica')
        complete = all(key in charts for key in ('sales_trend', 'payment_methods', 'cash_closures'))
        self.charts_notice.setText(
            'Stock y pendientes muestran el último reporte recibido. Las ventas y los arqueos corresponden al período elegido.'
            if complete else 'Sin información gráfica completa. Administración debe actualizar la configuración de reportes; las tablas y los totales recibidos siguen disponibles.'
        )
        for widget in list(self.cards.values()) + [self.trend_chart, self.branch_chart, self.payment_chart, self.stock_chart, self.cash_chart]:
            widget.set_stale(False)

    @staticmethod
    def _table(headers):
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True)
        return table

    def is_running(self):
        return self.worker is not None

    def _kind(self):
        return self.KINDS[self.tabs.currentIndex()]

    def _params(self):
        return {
            'branch_id': self.branch.currentData(),
            'fecha_desde': self.date_from.date().toString('yyyy-MM-dd'),
            'fecha_hasta': self.date_to.date().toString('yyyy-MM-dd'),
            'kind': self._kind(), 'page': self.page,
        }

    def _authorized(self):
        try:
            return _admin()
        except Exception as exc:
            self.valid_snapshot = False
            self._mark_stale()
            self.status.setText(str(exc))
            self.setEnabled(False)
            return None

    def filters_changed(self, *args):
        self.page = 0
        self.generation += 1
        self.valid_snapshot = False
        self._mark_stale()
        self.has_more = False
        self.status.setText('Filtros modificados. Pulse Actualizar; los datos anteriores no corresponden a esta consulta.')
        self._update_buttons()

    def tab_changed(self, *args):
        self.filters_changed()
        self.refresh()

    def refresh(self):
        user = self._authorized()
        if not user or self.stopped or self.is_running():
            return
        if self.date_from.date() > self.date_to.date():
            self.status.setText('La fecha Desde no puede ser posterior a Hasta.')
            return
        self.valid_snapshot = False
        self._mark_stale()
        self.status.setText('Consultando Supabase… Las sucursales sin conexión pueden tener datos pendientes.')
        self._start_worker('load', self._params(), user.user_id)

    def _start_worker(self, action, params, user_id):
        self._mark_stale()
        self.worker = CentralWorker(action, params, self.generation, user_id, self)
        self.worker.finished.connect(self.worker_finished)
        self._set_busy(True)
        self.worker.start()

    def _set_busy(self, busy):
        for control in (self.branch, self.date_from, self.date_to, self.refresh_button, self.tabs, *self.period_buttons.values()):
            control.setEnabled(not busy)
        self._update_buttons()

    def _update_buttons(self):
        busy = self.is_running() or self.stopped
        self.previous_button.setEnabled(not busy and self.valid_snapshot and self.page > 0)
        self.next_button.setEnabled(not busy and self.valid_snapshot and self.has_more)
        self.price_button.setEnabled(
            not busy and self.valid_snapshot and self._kind() == 'productos'
            and self.tables['productos'].currentRow() >= 0
        )
        self.price_button.setVisible(self._kind() == 'productos')
        self.page_label.setText(f'Página {self.page + 1} · hasta 100 registros')

    def change_page(self, delta):
        if not self._authorized() or self.is_running() or not self.valid_snapshot:
            return
        if delta > 0 and not self.has_more:
            return
        self.page = max(0, self.page + delta)
        self.generation += 1
        self.refresh()

    def worker_finished(self):
        worker = self.worker
        self.worker = None
        self._set_busy(False)
        try:
            user = AuthManager.current_user()
            if self.stopped:
                return
            if user is None or user.role != 'admin' or user.user_id != worker.user_id:
                self._authorized()
                self.valid_snapshot = False
                self.status.setText('La sesión cambió. Vuelva a iniciar sesión y consultar.')
                self.setEnabled(False)
                return
            if worker.generation != self.generation:
                self._mark_stale()
                self.status.setText('Se descartó una respuesta anterior. Pulse Actualizar con los filtros actuales.')
                return
            if worker.error:
                self.valid_snapshot = False
                self._mark_stale()
                self.status.setText('No se pudo actualizar: ' + worker.error + '. Los datos visibles son anteriores a este intento.')
                return
            if worker.action == 'price':
                self.valid_snapshot = False
                self.status.setText('Solicitud de precios enviada. Pendiente de confirmación de la sucursal; no se considera aplicada.')
                QMessageBox.information(
                    self, 'Solicitud registrada',
                    'El cambio quedó solicitado. Se aplicará cuando la sucursal lo reciba y confirme. '
                    'Consulte Cambios de precios: un CONFLICTO requiere revisar los precios actuales y crear una nueva solicitud.',
                )
            else:
                self._show_result(worker.result, worker.params['kind'])
        except Exception:
            self.valid_snapshot = False
            self._mark_stale()
            self.status.setText('No se pudo interpretar la respuesta. Los datos visibles no se consideran actualizados.')
        finally:
            worker.deleteLater()
            self._update_buttons()
            self.idle.emit()

    def _show_result(self, result, kind):
        dashboard = result['dashboard']
        selected = self.branch.currentData()
        for row in dashboard.get('branches', []):
            self.branch_names[row['id']] = row['nombre']
        self.branch.blockSignals(True)
        self.branch.clear()
        self.branch.addItem('Todas las sucursales', None)
        for branch_id, name in sorted(self.branch_names.items(), key=lambda pair: pair[1]):
            self.branch.addItem(name, branch_id)
        index = self.branch.findData(selected)
        self.branch.setCurrentIndex(max(0, index))
        self.branch.blockSignals(False)
        totals = dashboard.get('totals', {})
        self.summary.setText(
            f"Ventas: {_money(totals.get('total_vendido', 0))}   Operaciones: {totals.get('ventas_count', 0)}   "
            f"Productos: {totals.get('productos_count', 0)}   Alertas de stock: {totals.get('alertas_stock', 0)}   "
            f"Cierres: {totals.get('cierres_count', 0)}   Diferencias: {_money(totals.get('diferencias', 0))}"
        )
        branches = dashboard.get('branches', [])
        self._show_visuals(dashboard)
        self.branches_table.setRowCount(len(branches))
        for index, row in enumerate(branches):
            values = (row['nombre'], _time(row.get('last_sync_at')),
                      row.get('pendientes') if row.get('pendientes') is not None else 'Sin informe',
                      _money(row.get('total_vendido', 0)),
                      row.get('ventas_count', 0), row.get('productos_count', 0), row.get('alertas_stock', 0),
                      row.get('cierres_count', 0), _money(row.get('diferencias', 0)))
            for column, value in enumerate(values):
                self.branches_table.setItem(index, column, QTableWidgetItem(str(value)))
        page = result['page']
        self.rows[kind] = page.get('rows', [])
        self.has_more = bool(page.get('has_more'))
        table = self.tables[kind]
        table.setRowCount(len(self.rows[kind]))
        for index, row in enumerate(self.rows[kind]):
            for column, (_, key) in enumerate(self.COLUMNS[kind]):
                value = row.get(key)
                if key in self.MONEY_KEYS:
                    value = _money(value)
                elif key in ('fecha', 'fecha_cierre', 'creado_en'):
                    value = _time(value) if value else '-'
                table.setItem(index, column, QTableWidgetItem('-' if value is None else str(value)))
        self.loaded = True
        self.valid_snapshot = True
        suffix = '' if self.rows[kind] else ' · Sin registros para estos filtros.'
        self.status.setText(f"Consulta recibida: {_time(dashboard.get('fetched_at'))} · No es tiempo real.{suffix}")

    def request_price_change(self):
        user = self._authorized()
        if not user or self.stopped or self.is_running() or not self.valid_snapshot or self._kind() != 'productos':
            return
        index = self.tables['productos'].currentRow()
        if index < 0 or index >= len(self.rows['productos']):
            return
        product = self.rows['productos'][index]
        cash, ok = QInputDialog.getDouble(
            self, 'Precio contado', 'Nuevo precio de contado:', float(product.get('precio_contado') or 0), 0, 999999999.99, 2,
        )
        if not ok:
            return
        card, ok = QInputDialog.getDouble(
            self, 'Precio tarjeta', 'Nuevo precio de tarjeta:', float(product.get('precio_tarjeta') or 0), 0, 999999999.99, 2,
        )
        if not ok:
            return
        if not all(math.isfinite(value) and value >= 0 for value in (cash, card)):
            QMessageBox.warning(self, 'Precios inválidos', 'Los precios deben ser números finitos mayores o iguales a cero.')
            return
        branch_name = product.get('sucursal_nombre') or self.branch_names.get(product['sucursal_id'], product['sucursal_id'])
        answer = QMessageBox.question(
            self, 'Solicitar cambio de precios',
            f"Sucursal: {branch_name}\nProducto: {product['nombre']}\n"
            f"Contado: {_money(cash)}\nTarjeta: {_money(card)}\n\n"
            'Se enviará una solicitud; no modifica el stock. Si el precio local cambió, '
            'se informará un conflicto en lugar de sobrescribirlo. ¿Continuar?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        # La sesión puede haber cambiado mientras se mostraban los diálogos.
        user = self._authorized()
        if user is None:
            return
        self.status.setText('Registrando solicitud de precios…')
        self._start_worker('price', {
            'branch_id': product['sucursal_id'], 'product_id': product['id'],
            'expected_catalog_revision': product['catalog_revision'],
            'precio_contado': cash, 'precio_tarjeta': card,
        }, user.user_id)

    def showEvent(self, event):
        super().showEvent(event)
        if not self.loaded and not self.stopped:
            QTimer.singleShot(0, self.refresh)

    def stop(self):
        self.stopped = True
        self.generation += 1
