"""Acceso de operadores, con verificación de red fuera del hilo de interfaz."""
from PyQt6.QtCore import QThread
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QDialogButtonBox,
)

from src.core.auth_manager import AuthManager
from src.core.installation_store import get_installation


class LoginWorker(QThread):
    def __init__(self, username, password, parent=None, *, branch_code=None):
        super().__init__(parent)
        self.username = username
        self.password = password
        self.branch_code = branch_code
        self.session = None
        self.error = None

    def run(self):
        try:
            if self.branch_code is None:
                self.session = AuthManager.login(self.username, self.password)
            else:
                self.session = AuthManager.login(self.username, self.password, self.branch_code)
        except Exception as exc:
            self.error = str(exc)
        finally:
            self.password = None


class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(420)
        self.worker = None
        self.installation_error = None
        try:
            self.installation = get_installation()
        except Exception as exc:
            self.installation = None
            self.installation_error = str(exc)
        self.setup_mode = self.installation is None
        self.setWindowTitle("Configurar esta computadora" if self.setup_mode else "Iniciar sesión")
        layout = QVBoxLayout(self)
        self.title = QLabel("Configurar esta computadora" if self.setup_mode else self.installation['branch_name'])
        self.title.setStyleSheet("font-size: 22px; font-weight: bold; color: #0284C7;")
        layout.addWidget(self.title)
        instruction = QLabel(
            "Ingrese el código de sucursal y sus credenciales. La primera vinculación requiere internet."
            if self.setup_mode else "Ingrese con su usuario para registrar el responsable del turno."
        )
        instruction.setWordWrap(True)
        layout.addWidget(instruction)
        layout.addWidget(QLabel("Código de sucursal"))
        self.branch_code = QLineEdit()
        self.branch_code.setPlaceholderText("estacion-de-simoca")
        self.branch_code.setReadOnly(not self.setup_mode)
        if self.installation is not None:
            self.branch_code.setText(self.installation['branch_code'])
        layout.addWidget(self.branch_code)
        layout.addWidget(QLabel("Usuario"))
        self.username = QLineEdit("caja1")
        layout.addWidget(self.username)
        layout.addWidget(QLabel("Contraseña"))
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.returnPressed.connect(self.start_login)
        layout.addWidget(self.password)
        self.message = QLabel("El primer ingreso requiere conexión a internet." if self.setup_mode else "Ingrese con sus credenciales verificadas para esta sucursal.")
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        self.login_button = QPushButton("Vincular e ingresar" if self.setup_mode else "Ingresar")
        self.login_button.clicked.connect(self.start_login)
        layout.addWidget(self.login_button)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        if self.installation_error is not None:
            self.message.setText(f"No se pudo leer la configuración de esta computadora: {self.installation_error}")
            self.login_button.setEnabled(False)
            self.branch_code.setEnabled(False)

    def start_login(self):
        if self.installation_error is not None:
            return
        if self.worker is not None and self.worker.isRunning():
            return
        if not self.username.text().strip() or not self.password.text():
            self.message.setText("Complete el usuario y la contraseña.")
            return
        code = self.branch_code.text().strip()
        if self.setup_mode and not code:
            self.message.setText("Complete el código de sucursal asignado por administración.")
            self.branch_code.setFocus()
            return
        self.login_button.setEnabled(False)
        self.username.setEnabled(False)
        self.password.setEnabled(False)
        self.branch_code.setEnabled(False)
        self.buttons.setEnabled(False)
        self.message.setText("Verificando acceso…")
        self.worker = LoginWorker(
            self.username.text().strip(), self.password.text(), parent=self,
            branch_code=code if self.setup_mode else None,
        )
        self.password.clear()
        self.worker.finished.connect(self.login_finished)
        self.worker.start()

    def login_finished(self):
        worker = self.worker
        if worker.session is not None:
            self.accept()
        else:
            self.message.setText(worker.error or "No se pudo iniciar sesión.")
            self.login_button.setEnabled(True)
            self.username.setEnabled(True)
            self.password.setEnabled(True)
            self.branch_code.setEnabled(True)
            self.buttons.setEnabled(True)
            self.password.setFocus()
        worker.deleteLater()
        self.worker = None

    def reject(self):
        if self.worker is not None and self.worker.isRunning():
            self.message.setText("Espere a que termine la verificación de acceso.")
            return
        super().reject()

    def closeEvent(self, event):
        if self.worker is not None and self.worker.isRunning():
            event.ignore()
            return
        super().closeEvent(event)
