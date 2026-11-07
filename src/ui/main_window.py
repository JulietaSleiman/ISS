from PyQt6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QStackedWidget, QLabel, QMessageBox
from PyQt6.QtCore import Qt, QTimer
from src.ui.pos_view import POSView
from src.ui.productos_view import ProductosView
from src.ui.caja_view import CajaView
from src.ui.promociones_view import PromocionesView
from src.ui.reportes_view import ReportesView
from src.ui.clientes_view import ClientesView
from src.ui.proveedores_view import ProveedoresView
from src.ui.categorias_view import CategoriasView
from src.ui.deudores_view import DeudoresView
from src.ui.deudas_proveedores_view import DeudasProveedoresView
from src.core.updater import UpdateCheckerThread, UpdateDialog, CURRENT_VERSION
from src.core.auth_manager import AuthManager
from src.core.caja_manager import CajaManager
from src.ui.sync_controller import SyncController
from src.ui.central_view import CentralView

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.user = AuthManager.require_user()
        self.login_again = False
        self._close_requested = False
        self._cart_close_confirmed = False
        self.setWindowTitle(f"Sistema de Ventas - Ivan Llorens (v{CURRENT_VERSION})")
        self.resize(1200, 800)
        
        # Set Window Icon
        import os, sys
        from PyQt6.QtGui import QIcon
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            
        icon_path = os.path.join(base_path, "logo.ico")
        if not os.path.exists(icon_path):
            icon_path = os.path.join(base_path, "logo.png")
            if not os.path.exists(icon_path):
                icon_path = os.path.join(base_path, "logo.jpg")
        self.setWindowIcon(QIcon(icon_path))
        
        self.init_ui()
        self.sync_controller = SyncController(self)
        self.sync_controller.status_changed.connect(self.lbl_sync.setText)
        self.sync_controller.idle.connect(self._finish_requested_close)
        self.sync_controller.idle.connect(self._check_session)
        self.caja_view.caja_cerrada.connect(self.sync_controller.start)
        self.pos_view.venta_realizada.connect(self.sync_controller.start)
        if self.central_view is not None:
            self.central_view.idle.connect(self._finish_requested_close)
            self.central_view.idle.connect(self._check_session)
        QTimer.singleShot(0, self.sync_controller.start)
        self.verificar_actualizaciones()

    def verificar_actualizaciones(self):
        self.updater_thread = UpdateCheckerThread()
        self.updater_thread.update_available.connect(self.mostrar_dialogo_actualizacion)
        self.updater_thread.finished.connect(self._finish_requested_close)
        self.updater_thread.start()

    def mostrar_dialogo_actualizacion(self, release_info):
        if self._close_requested:
            return
        dialog = UpdateDialog(release_info, self)
        dialog.exec()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # --- Menú Lateral ---
        sidebar = QWidget()
        sidebar.setFixedWidth(260)
        sidebar.setStyleSheet("background-color: #FFFFFF; color: #0F172A; border-right: 1px solid #E2E8F0;")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(15, 15, 15, 15)
        sidebar_layout.setSpacing(6)

        # Título del menú (Logo)
        lbl_brand = QLabel()
        from PyQt6.QtGui import QPixmap
        import os
        import sys
        
        if getattr(sys, 'frozen', False):
            # En el .exe, los archivos añadidos están en _MEIPASS
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            
        logo_path = os.path.join(base_path, "logo.png")
        if not os.path.exists(logo_path):
            logo_path = os.path.join(base_path, "logo.jpg")
            
        pixmap = QPixmap(logo_path)
        if not pixmap.isNull():
            lbl_brand.setPixmap(pixmap.scaled(220, 110, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            lbl_brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_brand.setMinimumHeight(100)
            lbl_brand.setStyleSheet("margin-bottom: 10px; background: transparent;")
        else:
            lbl_brand.setText("IVAN LLORENS")
            lbl_brand.setStyleSheet("font-size: 22px; font-weight: 800; color: #0284C7; margin-bottom: 10px; border: none;")
        
        sidebar_layout.addWidget(lbl_brand)
        mode = "Acceso sin conexión" if self.user.offline else "Acceso verificado"
        self.lbl_user = QLabel(f"{self.user.branch_name}\nUsuario: {self.user.username}\n{mode}")
        self.lbl_user.setWordWrap(True)
        self.lbl_user.setStyleSheet("font-size: 13px; border: none; padding: 6px;")
        sidebar_layout.addWidget(self.lbl_user)
        self.lbl_sync = QLabel("Operaciones pendientes de comprobar")
        self.lbl_sync.setWordWrap(True)
        self.lbl_sync.setStyleSheet("font-size: 11px; color: #64748B; border: none; padding: 6px;")
        sidebar_layout.addWidget(self.lbl_sync)
        if AuthManager.cache_warning:
            warning = QLabel(AuthManager.cache_warning)
            warning.setWordWrap(True)
            warning.setStyleSheet("font-size: 11px; color: #B45309; border: none;")
            sidebar_layout.addWidget(warning)

        # Botones del menú
        self.btn_pos = self.crear_boton_menu("Punto de Venta")
        self.btn_productos = self.crear_boton_menu("Productos")
        self.btn_promociones = self.crear_boton_menu("Promociones (Combos)")
        self.btn_categorias = self.crear_boton_menu("Categorías/Rubros")
        self.btn_proveedores = self.crear_boton_menu("Proveedores")
        self.btn_deudas_proveedores = self.crear_boton_menu("Cuentas a Pagar (Prov.)")
        self.btn_clientes = self.crear_boton_menu("Clientes")
        self.btn_deudores = self.crear_boton_menu("Cuentas Ctes. (Fiado)")
        self.btn_caja = self.crear_boton_menu("Caja Diaria")
        self.btn_reportes = self.crear_boton_menu("Reportes")
        self.btn_central = None
        if self.user.role == 'admin':
            self.btn_central = self.crear_boton_menu("Administración central")
            sidebar_layout.addWidget(self.btn_central)

        sidebar_layout.addWidget(self.btn_pos)
        sidebar_layout.addWidget(self.btn_productos)
        sidebar_layout.addWidget(self.btn_promociones)
        sidebar_layout.addWidget(self.btn_categorias)
        sidebar_layout.addWidget(self.btn_proveedores)
        sidebar_layout.addWidget(self.btn_deudas_proveedores)
        sidebar_layout.addWidget(self.btn_clientes)
        sidebar_layout.addWidget(self.btn_deudores)
        sidebar_layout.addWidget(self.btn_caja)
        sidebar_layout.addWidget(self.btn_reportes)
        sidebar_layout.addStretch()
        self.btn_logout = QPushButton("Cerrar sesión")
        self.btn_logout.clicked.connect(self.cerrar_sesion)
        sidebar_layout.addWidget(self.btn_logout)

        # --- Área Central (Stack de Vistas) ---
        self.stacked_widget = QStackedWidget()
        
        # Inicializar vistas
        self.pos_view = POSView()
        self.productos_view = ProductosView()
        self.promociones_view = PromocionesView()
        self.categorias_view = CategoriasView()
        self.proveedores_view = ProveedoresView()
        self.deudas_proveedores_view = DeudasProveedoresView()
        self.clientes_view = ClientesView()
        self.deudores_view = DeudoresView()
        self.caja_view = CajaView()
        self.reportes_view = ReportesView()
        self.central_view = CentralView() if self.user.role == 'admin' else None
        
        # Agregar vistas al stack
        self.stacked_widget.addWidget(self.pos_view)
        self.stacked_widget.addWidget(self.productos_view)
        self.stacked_widget.addWidget(self.promociones_view)
        self.stacked_widget.addWidget(self.categorias_view)
        self.stacked_widget.addWidget(self.proveedores_view)
        self.stacked_widget.addWidget(self.deudas_proveedores_view)
        self.stacked_widget.addWidget(self.clientes_view)
        self.stacked_widget.addWidget(self.deudores_view)
        self.stacked_widget.addWidget(self.caja_view)
        self.stacked_widget.addWidget(self.reportes_view)
        if self.central_view is not None:
            self.stacked_widget.addWidget(self.central_view)
            self.btn_central.clicked.connect(self.mostrar_administracion_central)

        # Conectar botones a las vistas
        self.btn_pos.clicked.connect(lambda: self.stacked_widget.setCurrentWidget(self.pos_view))
        
        # Sincronización de vistas (cuando se vende algo, actualizar las grillas)
        self.pos_view.venta_realizada.connect(self.productos_view.cargar_grilla)
        
        def show_productos_view():
            self.productos_view.cargar_combos()
            self.stacked_widget.setCurrentWidget(self.productos_view)
            
        self.btn_productos.clicked.connect(show_productos_view)
        self.btn_promociones.clicked.connect(lambda: self.stacked_widget.setCurrentWidget(self.promociones_view))
        self.btn_categorias.clicked.connect(lambda: self.stacked_widget.setCurrentWidget(self.categorias_view))
        self.btn_proveedores.clicked.connect(lambda: self.stacked_widget.setCurrentWidget(self.proveedores_view))
        self.btn_deudas_proveedores.clicked.connect(lambda: self.stacked_widget.setCurrentWidget(self.deudas_proveedores_view))
        self.btn_clientes.clicked.connect(lambda: self.stacked_widget.setCurrentWidget(self.clientes_view))
        self.btn_deudores.clicked.connect(lambda: self.stacked_widget.setCurrentWidget(self.deudores_view))
        self.btn_caja.clicked.connect(lambda: self.stacked_widget.setCurrentWidget(self.caja_view))
        self.btn_reportes.clicked.connect(lambda: self.stacked_widget.setCurrentWidget(self.reportes_view))

        # Agregar todo al layout principal
        main_layout.addWidget(sidebar)
        main_layout.addWidget(self.stacked_widget)

        
        # Establecer padding 0
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        if self.central_view is not None:
            self.stacked_widget.setCurrentWidget(self.central_view)
            self.btn_central.setChecked(True)
        else:
            self.btn_pos.setChecked(True)

    def mostrar_administracion_central(self):
        user = AuthManager.current_user()
        if user is None or user.role != 'admin' or self.central_view is None:
            QMessageBox.warning(self, "Acceso restringido", "Esta vista requiere una cuenta administradora.")
            return
        self.stacked_widget.setCurrentWidget(self.central_view)

    def cerrar_sesion(self):
        try:
            if CajaManager.obtener_sesion_activa():
                QMessageBox.warning(self, "Turno abierto", "Cierre el turno antes de cambiar de usuario.")
                return
        except Exception as exc:
            QMessageBox.warning(self, "Revisar turno", str(exc))
            return
        if self.pos_view.carrito:
            QMessageBox.warning(self, "Venta pendiente", "Termine o cancele la venta antes de cerrar sesión.")
            return
        self.login_again = True
        self.close()

    def _finish_requested_close(self):
        if self._close_requested:
            QTimer.singleShot(0, self.close)

    def _check_session(self):
        session = AuthManager.current_user()
        if session is not None:
            self.user = session
            mode = "Acceso sin conexión" if session.offline else "Acceso verificado"
            self.lbl_user.setText(f"{session.branch_name}\nUsuario: {session.username}\n{mode}")
        elif not self._close_requested:
            self.centralWidget().setEnabled(False)
            self.login_again = True
            QMessageBox.warning(
                self, "Sesión no válida",
                "El servidor rechazó la sesión. Las operaciones locales guardadas se conservan. "
                "Vuelva a iniciar sesión para continuar.",
            )
            self.close()

    def closeEvent(self, event):
        sync = getattr(self, 'sync_controller', None)
        updater = getattr(self, 'updater_thread', None)
        central = getattr(self, 'central_view', None)
        if self.pos_view.carrito and not self._cart_close_confirmed:
            reply = QMessageBox.question(
                self, "Venta pendiente", "Hay una venta sin cobrar. ¿Salir y descartar el carrito?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._cart_close_confirmed = True
        if sync is not None:
            sync.stop()
        if central is not None:
            central.stop()
        if ((sync is not None and sync.is_running()) or (updater is not None and updater.isRunning())
                or (central is not None and central.is_running())):
            self._close_requested = True
            self.centralWidget().setEnabled(False)
            self.lbl_sync.setText("Esperando que termine la conexión para cerrar… Los datos locales están guardados.")
            event.ignore()
            return
        event.accept()

    def crear_boton_menu(self, texto):
        btn = QPushButton(texto)
        btn.setFixedHeight(44)
        btn.setCheckable(True)
        btn.setAutoExclusive(True)
        btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #475569;
                border: none;
                border-radius: 8px;
                font-size: 15px;
                font-weight: 600;
                text-align: left;
                padding-left: 20px;
            }
            QPushButton:hover {
                background-color: #F1F5F9;
                color: #0F172A;
            }
            QPushButton:pressed {
                background-color: #E2E8F0;
                color: #0284C7;
            }
            QPushButton:checked {
                background-color: #E0F2FE;
                color: #0284C7;
                border-left: 4px solid #0284C7;
                border-top-left-radius: 4px;
                border-bottom-left-radius: 4px;
            }
        """)
        return btn
