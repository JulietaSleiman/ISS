"""Reintentos de operaciones pendientes sin bloquear las ventas."""
from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal

from src.core.sync_manager import SyncManager


class SyncWorker(QThread):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.result = None

    def run(self):
        try:
            self.result = SyncManager.sync_pending()
        except Exception:
            self.result = {'sent': 0, 'pending': None, 'error': 'No se pudo sincronizar. Se reintentará.'}


class SyncController(QObject):
    status_changed = pyqtSignal(str)
    catalog_changed = pyqtSignal()
    idle = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = None
        self.stopped = False
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(5000)
        self.timer.timeout.connect(self.start)
        self.timer.start()

    def is_running(self):
        return self.worker is not None

    def start(self):
        if self.stopped or self.worker is not None:
            return
        self.timer.stop()
        self.status_changed.emit("Comprobando operaciones pendientes…")
        self.worker = SyncWorker(self)
        self.worker.finished.connect(self.finished)
        self.worker.start()

    def finished(self):
        worker = self.worker
        result = worker.result or {}
        pending = result.get('pending')
        if result.get('error'):
            count = f"{pending} operación(es) pendiente(s). " if pending is not None else ""
            self.status_changed.emit(count + "Sincronización pendiente: " + result['error'])
        elif pending:
            self.status_changed.emit(f"{pending} operación(es) pendiente(s) de envío.")
        else:
            self.status_changed.emit("No hay operaciones pendientes de envío")
        worker.deleteLater()
        self.worker = None
        self.idle.emit()
        if self.stopped:
            return
        if result.get('catalog_changed'):
            self.catalog_changed.emit()
        self.timer.start(5000 if result.get('catalog_checked') else 15000)

    def stop(self):
        self.stopped = True
        self.timer.stop()
