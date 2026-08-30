from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTableWidget, 
    QTableWidgetItem, QPushButton, QHeaderView, QMessageBox, QFrame, QSplitter
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from src.core.promociones_manager import PromocionesManager
from src.core.productos_manager import ProductosManager
from src.ui.buscador_productos import BuscadorProductosDialog

class PromocionesView(QWidget):
    def __init__(self):
        super().__init__()
        self.detalles_combo = [] # Lista de dicts: {'producto_id': 1, 'nombre': 'Coca', 'cantidad': 1}
        self.promocion_editando_id = None
        self.todas_promos = []
        self.init_ui()
        self.cargar_grilla()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        lbl_titulo = QLabel("MANTENIMIENTO DE PROMOCIONES (COMBOS)")
        lbl_titulo.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        lbl_titulo.setStyleSheet("color: #ACE0F4; margin-bottom: 10px;")
        layout.addWidget(lbl_titulo)

        splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(splitter)

        # --- PANEL SUPERIOR: FORMULARIO ---
        form_widget = QFrame()
        form_widget.setStyleSheet("""
            QFrame { background-color: #1A2026; border: 1px solid #32404D; border-radius: 8px; }
            QLabel { border: none; font-weight: bold; }
            
        """)
        form_layout = QVBoxLayout(form_widget)
        
        # Datos básicos
        basico_layout = QHBoxLayout()
        
        basico_layout.addWidget(QLabel("Nombre Promo:"))
        self.txt_nombre = QLineEdit()
        self.txt_nombre.setPlaceholderText("Ej. Promo Fernet + Coca")
        basico_layout.addWidget(self.txt_nombre)
        
        basico_layout.addWidget(QLabel("Precio Fijo: $"))
        self.txt_precio = QLineEdit()
        self.txt_precio.setFixedWidth(100)
        basico_layout.addWidget(self.txt_precio)
        
        form_layout.addLayout(basico_layout)

        # Agregar artículos al combo
        agregar_layout = QHBoxLayout()
        self.btn_buscar_art = QPushButton("Agregar Artículo al Combo (F2)")
        self.btn_buscar_art.setStyleSheet("background-color: #32404D; padding: 8px;")
        self.btn_buscar_art.clicked.connect(self.abrir_buscador)
        agregar_layout.addWidget(self.btn_buscar_art)
        agregar_layout.addStretch()
        form_layout.addLayout(agregar_layout)

        # Grilla de detalles del combo
        self.tabla_detalles = QTableWidget(0, 3)
        self.tabla_detalles.setHorizontalHeaderLabels(["Producto", "Cantidad Requerida", "Acción"])
        self.tabla_detalles.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tabla_detalles.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tabla_detalles.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.tabla_detalles.verticalHeader().setDefaultSectionSize(40)
        self.tabla_detalles.setFixedHeight(200)
        form_layout.addWidget(self.tabla_detalles)

        # Botones de Acción
        btn_layout = QHBoxLayout()
        self.btn_limpiar = QPushButton("Cancelar Edición / Limpiar")
        self.btn_limpiar.clicked.connect(self.limpiar_formulario)
        
        self.btn_grabar = QPushButton("Guardar Promoción")
        self.btn_grabar.setStyleSheet("background-color: #8DE2B9; color: #161B22; font-weight: bold; border: none;")
        self.btn_grabar.clicked.connect(self.guardar_promocion)

        btn_layout.addWidget(self.btn_limpiar)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_grabar)
        form_layout.addLayout(btn_layout)
        
        splitter.addWidget(form_widget)

        # --- PANEL INFERIOR: PROMOCIONES ACTIVAS ---
        grid_widget = QWidget()
        grid_layout = QVBoxLayout(grid_widget)
        grid_layout.setContentsMargins(0,10,0,0)

        grid_layout.addWidget(QLabel("Promociones Activas:"))
        self.tabla_promos = QTableWidget(0, 4)
        self.tabla_promos.setHorizontalHeaderLabels(["ID", "Nombre", "Precio Fijo", "Acción"])
        self.tabla_promos.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tabla_promos.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tabla_promos.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.tabla_promos.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.tabla_promos.verticalHeader().setDefaultSectionSize(40)
        self.tabla_promos.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla_promos.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        grid_layout.addWidget(self.tabla_promos)

        splitter.addWidget(grid_widget)

    def abrir_buscador(self):
        dialog = BuscadorProductosDialog(self)
        if dialog.exec():
            if dialog.codigo_seleccionado:
                prod = ProductosManager.get_by_codigo(dialog.codigo_seleccionado)
                if prod:
                    self.agregar_detalle(prod['id'], prod['nombre'])

    def agregar_detalle(self, producto_id, nombre):
        # Si ya existe, sumar 1
        for d in self.detalles_combo:
            if d['producto_id'] == producto_id:
                d['cantidad'] += 1
                self.actualizar_tabla_detalles()
                return
                
        self.detalles_combo.append({'producto_id': producto_id, 'nombre': nombre, 'cantidad': 1})
        self.actualizar_tabla_detalles()

    def actualizar_tabla_detalles(self):
        self.tabla_detalles.setRowCount(0)
        for i, d in enumerate(self.detalles_combo):
            self.tabla_detalles.insertRow(i)
            self.tabla_detalles.setItem(i, 0, QTableWidgetItem(d['nombre']))
            
            txt_cant = QLineEdit(str(d['cantidad']))
            txt_cant.setAlignment(Qt.AlignmentFlag.AlignCenter)
            txt_cant.textChanged.connect(lambda text, idx=i: self.cambiar_cantidad_detalle(idx, text))
            self.tabla_detalles.setCellWidget(i, 1, txt_cant)
            
            btn_quitar = QPushButton("Quitar")
            btn_quitar.setStyleSheet("background-color: #E28D8D; color: #161B22; font-weight: bold; padding: 5px;")
            btn_quitar.clicked.connect(lambda checked, idx=i: self.quitar_detalle(idx))
            self.tabla_detalles.setCellWidget(i, 2, btn_quitar)

    def cambiar_cantidad_detalle(self, idx, text):
        try:
            val = int(text)
            if val > 0:
                self.detalles_combo[idx]['cantidad'] = val
        except:
            pass

    def quitar_detalle(self, idx):
        self.detalles_combo.pop(idx)
        self.actualizar_tabla_detalles()

    def limpiar_formulario(self):
        self.promocion_editando_id = None
        self.txt_nombre.clear()
        self.txt_precio.clear()
        self.detalles_combo = []
        self.actualizar_tabla_detalles()
        self.btn_grabar.setText("Guardar Promoción")
        self.btn_grabar.setStyleSheet("background-color: #8DE2B9; color: #161B22; font-weight: bold; border: none;")

    def guardar_promocion(self):
        nombre = self.txt_nombre.text().strip()
        try:
            precio = float(self.txt_precio.text())
        except ValueError:
            QMessageBox.warning(self, "Error", "Precio inválido.")
            return

        if not nombre or not self.detalles_combo:
            QMessageBox.warning(self, "Error", "Debe ingresar un nombre y al menos un artículo para el combo.")
            return

        detalles_db = [{'producto_id': d['producto_id'], 'cantidad_requerida': d['cantidad']} for d in self.detalles_combo]
        
        try:
            if self.promocion_editando_id:
                PromocionesManager.actualizar_promocion(self.promocion_editando_id, nombre, precio, detalles_db)
                QMessageBox.information(self, "Éxito", "Promoción actualizada.")
            else:
                PromocionesManager.crear_promocion(nombre, precio, detalles_db)
                QMessageBox.information(self, "Éxito", "Promoción creada.")
            
            self.limpiar_formulario()
            self.cargar_grilla()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al guardar promoción:\n{str(e)}")

    def cargar_grilla(self):
        self.tabla_promos.setRowCount(0)
        self.todas_promos = PromocionesManager.get_all()
        for p in self.todas_promos:
            row = self.tabla_promos.rowCount()
            self.tabla_promos.insertRow(row)
            self.tabla_promos.setItem(row, 0, QTableWidgetItem(str(p['id'])))
            self.tabla_promos.setItem(row, 1, QTableWidgetItem(p['nombre']))
            self.tabla_promos.setItem(row, 2, QTableWidgetItem(f"${p['precio_fijo']:.2f}"))
            
            # Contenedor para botones de acción
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(0, 0, 0, 0)
            
            btn_editar = QPushButton("Editar")
            btn_editar.setStyleSheet("background-color: #F0DA8C; color: #161B22; font-weight: bold; padding: 5px;")
            btn_editar.clicked.connect(lambda checked, pid=p['id']: self.cargar_para_editar(pid))
            
            btn_eliminar = QPushButton("Eliminar")
            btn_eliminar.setStyleSheet("background-color: #E28D8D; color: #161B22; font-weight: bold; padding: 5px;")
            btn_eliminar.clicked.connect(lambda checked, pid=p['id']: self.eliminar_promocion(pid))
            
            action_layout.addWidget(btn_editar)
            action_layout.addWidget(btn_eliminar)
            
            self.tabla_promos.setCellWidget(row, 3, action_widget)

    def cargar_para_editar(self, pid):
        promo = next((p for p in self.todas_promos if p['id'] == pid), None)
        if not promo:
            return
            
        self.promocion_editando_id = promo['id']
        self.txt_nombre.setText(promo['nombre'])
        self.txt_precio.setText(str(promo['precio_fijo']))
        
        self.detalles_combo = []
        for d in promo['detalles']:
            prod = ProductosManager.get_by_id(d['producto_id'])
            if prod:
                self.detalles_combo.append({
                    'producto_id': d['producto_id'],
                    'nombre': prod['nombre'],
                    'cantidad': d['cantidad_requerida']
                })
        
        self.actualizar_tabla_detalles()
        
        self.btn_grabar.setText("Actualizar Promoción")
        self.btn_grabar.setStyleSheet("background-color: #F0DA8C; color: #161B22; font-weight: bold; border: none;")

    def eliminar_promocion(self, pid):
        reply = QMessageBox.question(self, "Confirmar", "¿Eliminar esta promoción?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            PromocionesManager.eliminar_promocion(pid)
            self.cargar_grilla()
