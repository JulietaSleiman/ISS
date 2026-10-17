from PyQt6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QStackedWidget, QLabel
from PyQt6.QtCore import Qt
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

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
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
        self.verificar_actualizaciones()

    def verificar_actualizaciones(self):
        self.updater_thread = UpdateCheckerThread()
        self.updater_thread.update_available.connect(self.mostrar_dialogo_actualizacion)
        self.updater_thread.start()

    def mostrar_dialogo_actualizacion(self, release_info):
        dialog = UpdateDialog(release_info, self)
        dialog.exec()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # --- Menú Lateral ---
        sidebar = QWidget()
        sidebar.setFixedWidth(260)
        sidebar.setStyleSheet("background-color: #161B22; color: #E5EEF2; border-right: 1px solid #232B33;")
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
            lbl_brand.setStyleSheet("font-size: 22px; font-weight: 800; color: #ACE0F4; margin-bottom: 10px; border: none;")
        
        sidebar_layout.addWidget(lbl_brand)

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
        
        self.btn_pos.setChecked(True)

    def crear_boton_menu(self, texto):
        btn = QPushButton(texto)
        btn.setFixedHeight(44)
        btn.setCheckable(True)
        btn.setAutoExclusive(True)
        btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #9EB3C2;
                border: none;
                border-radius: 8px;
                font-size: 15px;
                font-weight: 600;
                text-align: left;
                padding-left: 20px;
            }
            QPushButton:hover {
                background-color: #232B33;
                color: #E5EEF2;
            }
            QPushButton:pressed {
                background-color: #32404D;
                color: #ACE0F4;
            }
            QPushButton:checked {
                background-color: #232B33;
                color: #ACE0F4;
                border-left: 4px solid #ACE0F4;
                border-top-left-radius: 4px;
                border-bottom-left-radius: 4px;
            }
        """)
        return btn
