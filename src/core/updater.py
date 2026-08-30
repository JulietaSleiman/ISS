import os
import sys
import json
import urllib.request
import subprocess
from packaging import version
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressBar, QPushButton, QHBoxLayout, QMessageBox, QApplication

CURRENT_VERSION = "1.0.0"
GITHUB_REPO = "BernabeFigueroa/BF"  # Repositorio oficial para releases/binarios
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

class UpdateCheckerThread(QThread):
    update_available = pyqtSignal(dict)  # Emite datos del release si hay actualización
    no_update = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def run(self):
        try:
            req = urllib.request.Request(
                GITHUB_API_URL,
                headers={"User-Agent": "BebidasFrias-AutoUpdater"}
            )
            with urllib.request.urlopen(req, timeout=6) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode())
                    tag_name = data.get("tag_name", "").lstrip("v").strip()
                    
                    if not tag_name:
                        self.no_update.emit()
                        return

                    # Comparar versiones de forma semántica
                    if version.parse(tag_name) > version.parse(CURRENT_VERSION):
                        download_url = None
                        exe_size = 0
                        
                        # Determinar el nombre exacto del ejecutable en ejecución
                        current_exe_name = os.path.basename(sys.executable).lower() if getattr(sys, 'frozen', False) else "sistemabebidas.exe"
                        
                        assets = data.get("assets", [])
                        # 1. Buscar coincidencia exacta por nombre
                        for asset in assets:
                            asset_name = asset.get("name", "").lower()
                            if asset_name == current_exe_name:
                                download_url = asset.get("browser_download_url")
                                exe_size = asset.get("size", 0)
                                break
                        
                        # 2. Si no hay coincidencia exacta pero solo hay 1 ejecutable genérico en el repo
                        if not download_url:
                            for asset in assets:
                                if asset.get("name", "").lower().endswith(".exe"):
                                    download_url = asset.get("browser_download_url")
                                    exe_size = asset.get("size", 0)
                                    break
                        
                        if download_url:
                            self.update_available.emit({
                                "version": tag_name,
                                "download_url": download_url,
                                "body": data.get("body", "Mejoras generales y correcciones de errores."),
                                "size": exe_size
                            })
                        else:
                            self.no_update.emit()
                    else:
                        self.no_update.emit()
                else:
                    self.no_update.emit()
        except Exception as e:
            # Si no hay internet o aún no hay release en GitHub, continúa silenciosamente
            self.error_occurred.emit(str(e))


class DownloadWorkerThread(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, download_url, target_path):
        super().__init__()
        self.download_url = download_url
        self.target_path = target_path

    def run(self):
        try:
            req = urllib.request.Request(
                self.download_url,
                headers={"User-Agent": "BebidasFrias-AutoUpdater"}
            )
            with urllib.request.urlopen(req, timeout=30) as response:
                total_size = response.headers.get('content-length')
                if total_size:
                    total_size = int(total_size)
                else:
                    total_size = None

                bytes_downloaded = 0
                block_size = 65536  # 64 KB por bloque para máxima velocidad

                with open(self.target_path, 'wb') as f:
                    while True:
                        buffer = response.read(block_size)
                        if not buffer:
                            break
                        f.write(buffer)
                        bytes_downloaded += len(buffer)
                        if total_size and total_size > 0:
                            percent = int((bytes_downloaded / total_size) * 100)
                            self.progress.emit(percent)

            self.finished.emit(self.target_path)
        except Exception as e:
            self.error.emit(str(e))


class UpdateDialog(QDialog):
    def __init__(self, release_info, parent=None):
        super().__init__(parent)
        self.release_info = release_info
        self.setWindowTitle("Actualización Disponible - Bebidas Frías")
        self.setFixedSize(500, 270)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.setup_ui()

    def setup_ui(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #1A2026;
                color: #E5EEF2;
            }
            QLabel {
                color: #E5EEF2;
            }
            QPushButton {
                background-color: #32404D;
                color: #E5EEF2;
                border: 1px solid #425961;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
                padding: 8px 16px;
                min-height: 32px;
            }
            QPushButton:hover {
                background-color: #2C3742;
                border-color: #91C2D5;
                color: #ACE0F4;
            }
            QPushButton#btn_update {
                background-color: #8DE2B9;
                color: #161B22;
                border: none;
            }
            QPushButton#btn_update:hover {
                background-color: #7BCFA6;
            }
            QPushButton#btn_cancel {
                background-color: #232B33;
                color: #9EB3C2;
            }
            QPushButton#btn_cancel:hover {
                background-color: #32404D;
                color: #E5EEF2;
            }
            QProgressBar {
                border: 1px solid #32404D;
                border-radius: 6px;
                background-color: #232B33;
                text-align: center;
                color: #E5EEF2;
                font-weight: bold;
                height: 22px;
            }
            QProgressBar::chunk {
                background-color: #8DE2B9;
                border-radius: 5px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        lbl_title = QLabel(f"¡Nueva versión disponible: v{self.release_info['version']}!")
        lbl_title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        lbl_title.setStyleSheet("color: #ACE0F4;")
        layout.addWidget(lbl_title)

        lbl_desc = QLabel(
            f"Se ha publicado una actualización para el Sistema Bebidas Frías.\n"
            f"Versión actual: v{CURRENT_VERSION} -> Nueva: v{self.release_info['version']}\n\n"
            f"Haga clic en 'Actualizar e Instalar' para descargar e iniciar la versión más reciente."
        )
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet("color: #9EB3C2; font-size: 12px;")
        layout.addWidget(lbl_desc)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color: #ACE0F4; font-size: 11px; font-style: italic;")
        self.lbl_status.setVisible(False)
        layout.addWidget(self.lbl_status)

        layout.addStretch()

        btn_layout = QHBoxLayout()
        self.btn_cancel = QPushButton("Omitir por ahora")
        self.btn_cancel.setObjectName("btn_cancel")
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_update = QPushButton("Actualizar e Instalar")
        self.btn_update.setObjectName("btn_update")
        self.btn_update.clicked.connect(self.start_download)

        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_update)
        layout.addLayout(btn_layout)

    def start_download(self):
        self.btn_update.setEnabled(False)
        self.btn_cancel.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.lbl_status.setVisible(True)
        self.lbl_status.setText("Descargando actualización desde GitHub...")

        import tempfile
        temp_dir = tempfile.gettempdir()
        new_exe_path = os.path.join(temp_dir, "SistemaBebidas_update.exe")

        self.worker = DownloadWorkerThread(self.release_info["download_url"], new_exe_path)
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.finished.connect(self.on_download_finished)
        self.worker.error.connect(self.on_download_error)
        self.worker.start()

    def on_download_finished(self, new_exe_path):
        self.lbl_status.setText("Descarga finalizada. Aplicando actualización...")
        apply_update_and_restart(new_exe_path)
        self.accept()

    def on_download_error(self, error_msg):
        self.lbl_status.setText("Error en la descarga.")
        QMessageBox.warning(self, "Error de actualización", f"No se pudo descargar la actualización:\n{error_msg}")
        self.btn_update.setEnabled(True)
        self.btn_cancel.setEnabled(True)


def apply_update_and_restart(new_exe_path):
    """
    Ejecuta el reemplazo seguro del ejecutable y vuelve a iniciar la app.
    Maneja procesos en ejecución y permisos en Windows.
    """
    if not getattr(sys, 'frozen', False):
        QMessageBox.information(None, "Modo Desarrollo", f"Descargado con éxito en:\n{new_exe_path}\n(En modo ejecutable se aplica el reemplazo automático y reinicio)")
        return

    import tempfile
    current_exe = os.path.abspath(sys.executable)
    exe_name = os.path.basename(current_exe)
    pid = os.getpid()
    temp_dir = tempfile.gettempdir()
    updater_bat = os.path.join(temp_dir, "update_bebidasfrias.bat")
    backup_exe = current_exe + ".old"

    bat_content = f"""@echo off
chcp 65001 >nul
title Actualizando Sistema Bebidas Frias...

:: 1. Esperar un instante y forzar cierre de todos los procesos del ejecutable
timeout /t 1 /nobreak >nul
taskkill /F /T /PID {pid} >nul 2>&1
taskkill /F /IM "{exe_name}" >nul 2>&1

:: 2. Limpiar backup previo si existiera
if exist "{backup_exe}" del /F /Q "{backup_exe}" >nul 2>&1

:: 3. Reintentos de reemplazo
set ATTEMPTS=0
:RETRY
set /a ATTEMPTS+=1

move /Y "{current_exe}" "{backup_exe}" >nul 2>&1
if %ERRORLEVEL% equ 0 goto DO_COPY

copy /Y "{new_exe_path}" "{current_exe}" >nul 2>&1
if %ERRORLEVEL% equ 0 goto FINISH

if %ATTEMPTS% lss 30 (
    timeout /t 1 /nobreak >nul
    taskkill /F /IM "{exe_name}" >nul 2>&1
    goto RETRY
)

:DO_COPY
copy /Y "{new_exe_path}" "{current_exe}" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    move /Y "{new_exe_path}" "{current_exe}" >nul 2>&1
)

:FINISH
if exist "{backup_exe}" del /F /Q "{backup_exe}" >nul 2>&1
if exist "{new_exe_path}" del /F /Q "{new_exe_path}" >nul 2>&1

echo Iniciando nueva version...
start "" "{current_exe}"

:: Limpiar el propio script batch
(goto) 2>nul & del "%~f0"
exit
"""

    try:
        with open(updater_bat, "w", encoding="utf-8") as f:
            f.write(bat_content)

        # Lanzar el proceso batch en una nueva consola independiente para que sobreviva a la muerte del padre
        flags = subprocess.CREATE_NEW_PROCESS_GROUP
        if hasattr(subprocess, 'DETACHED_PROCESS'):
            flags |= subprocess.DETACHED_PROCESS
        
        subprocess.Popen(
            ["cmd.exe", "/c", updater_bat],
            creationflags=flags,
            close_fds=True
        )
    except Exception as e:
        print(f"Error lanzando updater: {e}")

    # Forzar salida inmediata del proceso para soltar todos los handles de Windows
    QApplication.quit()
    os._exit(0)
    sys.exit(0)

