from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTableWidget, 
    QTableWidgetItem, QPushButton, QHeaderView, QMessageBox, QFrame, QSplitter
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from src.core.proveedores_manager import ProveedoresManager

class ProveedoresView(QWidget):
    def __init__(self):
        super().__init__()
        self.prov_id_actual = None
        self.init_ui()
        self.cargar_grilla()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        lbl_titulo = QLabel("GESTIÓN DE PROVEEDORES")
        lbl_titulo.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        lbl_titulo.setStyleSheet("color: #ACE0F4; margin-bottom: 10px;")
        layout.addWidget(lbl_titulo)

        splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(splitter)

        # --- FORMULARIO ---
        form_widget = QFrame()
        form_widget.setStyleSheet("QFrame { background-color: #1A2026; border-radius: 8px; } QLabel { font-weight: bold; } QLineEdit { background-color: #32404D; border: 1px solid #32404D; padding: 5px; }")
        form_layout = QVBoxLayout(form_widget)
        
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Nombre/Razón Social:"))
        self.txt_nombre = QLineEdit()
        row1.addWidget(self.txt_nombre)
        
        row1.addWidget(QLabel("Teléfono:"))
        self.txt_telefono = QLineEdit()
        row1.addWidget(self.txt_telefono)
        form_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Dirección:"))
        self.txt_direccion = QLineEdit()
        row2.addWidget(self.txt_direccion)
        form_layout.addLayout(row2)

        # Botones
        btn_layout = QHBoxLayout()
        self.btn_limpiar = QPushButton("Limpiar / Nuevo")
        self.btn_limpiar.clicked.connect(self.limpiar_form)
        
        self.btn_eliminar = QPushButton("Dar de Baja")
        self.btn_eliminar.setStyleSheet("background-color: #E28D8D; color: #161B22; font-weight: bold; border: none;")
        self.btn_eliminar.clicked.connect(self.eliminar)
        self.btn_eliminar.setEnabled(False)
        
        self.btn_guardar = QPushButton("Guardar")
        self.btn_guardar.setStyleSheet("background-color: #8DE2B9; color: #161B22; font-weight: bold; border: none;")
        self.btn_guardar.clicked.connect(self.guardar)

        btn_layout.addWidget(self.btn_limpiar)
        btn_layout.addWidget(self.btn_eliminar)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_guardar)
        form_layout.addLayout(btn_layout)
        
        splitter.addWidget(form_widget)

        # --- GRILLA ---
        grid_widget = QWidget()
        grid_layout = QVBoxLayout(grid_widget)
        grid_layout.setContentsMargins(0, 10, 0, 0)
        
        self.tabla = QTableWidget(0, 4)
        self.tabla.setHorizontalHeaderLabels(["ID", "Nombre", "Teléfono", "Dirección"])
        self.tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.cellDoubleClicked.connect(self.seleccionar)
        grid_layout.addWidget(self.tabla)
        
        splitter.addWidget(grid_widget)

    def cargar_grilla(self):
        self.tabla.setRowCount(0)
        provs = ProveedoresManager.get_all()
        for p in provs:
            row = self.tabla.rowCount()
            self.tabla.insertRow(row)
            self.tabla.setItem(row, 0, QTableWidgetItem(str(p['id'])))
            self.tabla.setItem(row, 1, QTableWidgetItem(p['nombre']))
            self.tabla.setItem(row, 2, QTableWidgetItem(p['telefono'] or ""))
            self.tabla.setItem(row, 3, QTableWidgetItem(p['direccion'] or ""))

    def limpiar_form(self):
        self.prov_id_actual = None
        self.txt_nombre.clear()
        self.txt_telefono.clear()
        self.txt_direccion.clear()
        self.btn_eliminar.setEnabled(False)
        self.txt_nombre.setFocus()

    def seleccionar(self, row, col):
        self.prov_id_actual = int(self.tabla.item(row, 0).text())
        self.txt_nombre.setText(self.tabla.item(row, 1).text())
        self.txt_telefono.setText(self.tabla.item(row, 2).text())
        self.txt_direccion.setText(self.tabla.item(row, 3).text())
        self.btn_eliminar.setEnabled(True)

    def guardar(self):
        nombre = self.txt_nombre.text().strip()
        tel = self.txt_telefono.text().strip()
        dir = self.txt_direccion.text().strip()
        
        if not nombre:
            QMessageBox.warning(self, "Error", "El nombre es obligatorio.")
            return
            
        try:
            if self.prov_id_actual:
                ProveedoresManager.actualizar_proveedor(self.prov_id_actual, nombre, tel, dir)
            else:
                ProveedoresManager.crear_proveedor(nombre, tel, dir)
            self.limpiar_form()
            self.cargar_grilla()
            QMessageBox.information(self, "Éxito", "Proveedor guardado.")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def eliminar(self):
        if not self.prov_id_actual: return
        reply = QMessageBox.question(self, "Confirmar", "¿Dar de baja este proveedor?", 
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                ProveedoresManager.eliminar_proveedor(self.prov_id_actual)
                self.limpiar_form()
                self.cargar_grilla()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))
