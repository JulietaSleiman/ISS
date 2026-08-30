from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox, QTableWidget, 
    QTableWidgetItem, QPushButton, QHeaderView, QMessageBox, QFrame, QSplitter
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from src.core.clientes_manager import ClientesManager

class ClientesView(QWidget):
    def __init__(self):
        super().__init__()
        self.cliente_id_actual = None
        self.init_ui()
        self.cargar_grilla()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        lbl_titulo = QLabel("GESTIÓN DE CLIENTES")
        lbl_titulo.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        lbl_titulo.setStyleSheet("color: #ACE0F4; margin-bottom: 10px;")
        layout.addWidget(lbl_titulo)

        splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(splitter)

        # --- FORMULARIO ---
        form_widget = QFrame()
        form_widget.setStyleSheet("QFrame { background-color: #1A2026; border-radius: 8px; } QLabel { font-weight: bold; } QLineEdit, QComboBox { background-color: #32404D; border: 1px solid #32404D; padding: 5px; }")
        form_layout = QVBoxLayout(form_widget)
        
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Nombre/Razón Social:"))
        self.txt_nombre = QLineEdit()
        row1.addWidget(self.txt_nombre)
        row1.addWidget(QLabel("DNI/CUIT:"))
        self.txt_cuit = QLineEdit()
        row1.addWidget(self.txt_cuit)
        form_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Teléfono:"))
        self.txt_telefono = QLineEdit()
        row2.addWidget(self.txt_telefono)
        row2.addWidget(QLabel("Domicilio:"))
        self.txt_domicilio = QLineEdit()
        row2.addWidget(self.txt_domicilio)
        form_layout.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Condición IVA:"))
        self.cb_iva = QComboBox()
        self.cb_iva.addItems(["Consumidor Final", "Responsable Inscripto", "Monotributo", "Exento"])
        row3.addWidget(self.cb_iva)
        
        row3.addWidget(QLabel("Descuento Fijo (%):"))
        self.txt_descuento = QLineEdit("0.0")
        row3.addWidget(self.txt_descuento)
        form_layout.addLayout(row3)

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
        
        self.tabla = QTableWidget(0, 5)
        self.tabla.setHorizontalHeaderLabels(["ID", "Nombre", "DNI/CUIT", "Teléfono", "Descuento"])
        self.tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.cellDoubleClicked.connect(self.seleccionar)
        grid_layout.addWidget(self.tabla)
        
        splitter.addWidget(grid_widget)

    def cargar_grilla(self):
        self.tabla.setRowCount(0)
        clientes = ClientesManager.get_all()
        for p in clientes:
            row = self.tabla.rowCount()
            self.tabla.insertRow(row)
            self.tabla.setItem(row, 0, QTableWidgetItem(str(p['id'])))
            self.tabla.setItem(row, 1, QTableWidgetItem(p['nombre']))
            self.tabla.setItem(row, 2, QTableWidgetItem(p['cuit'] or ""))
            self.tabla.setItem(row, 3, QTableWidgetItem(p['telefono'] or ""))
            self.tabla.setItem(row, 4, QTableWidgetItem(f"{p['descuento_porcentaje']}%"))
            # Keep raw data for selection
            self.tabla.item(row, 0).setData(Qt.ItemDataRole.UserRole, p)

    def limpiar_form(self):
        self.cliente_id_actual = None
        self.txt_nombre.clear()
        self.txt_cuit.clear()
        self.txt_telefono.clear()
        self.txt_domicilio.clear()
        self.cb_iva.setCurrentIndex(0)
        self.txt_descuento.setText("0.0")
        self.btn_eliminar.setEnabled(False)
        self.txt_nombre.setFocus()

    def seleccionar(self, row, col):
        p = self.tabla.item(row, 0).data(Qt.ItemDataRole.UserRole)
        if not p: return
        self.cliente_id_actual = p['id']
        self.txt_nombre.setText(p['nombre'])
        self.txt_cuit.setText(p['cuit'] or "")
        self.txt_telefono.setText(p['telefono'] or "")
        self.txt_domicilio.setText(p['domicilio'] or "")
        self.cb_iva.setCurrentText(p['condicion_iva'] or "Consumidor Final")
        self.txt_descuento.setText(str(p['descuento_porcentaje'] or 0.0))
        
        self.btn_eliminar.setEnabled(self.cliente_id_actual != 1)

    def guardar(self):
        nombre = self.txt_nombre.text().strip()
        cuit = self.txt_cuit.text().strip()
        tel = self.txt_telefono.text().strip()
        dom = self.txt_domicilio.text().strip()
        iva = self.cb_iva.currentText()
        try:
            desc = float(self.txt_descuento.text())
        except:
            desc = 0.0
            
        if not nombre:
            QMessageBox.warning(self, "Error", "El nombre es obligatorio.")
            return
            
        try:
            if self.cliente_id_actual:
                ClientesManager.actualizar_cliente(self.cliente_id_actual, nombre, cuit, dom, "", "", iva, tel, "Contado", desc)
            else:
                ClientesManager.crear_cliente(nombre, cuit, dom, "", "", iva, tel, "Contado", desc)
            self.limpiar_form()
            self.cargar_grilla()
            QMessageBox.information(self, "Éxito", "Cliente guardado.")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def eliminar(self):
        if not self.cliente_id_actual or self.cliente_id_actual == 1: return
        reply = QMessageBox.question(self, "Confirmar", "¿Dar de baja este cliente?", 
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                ClientesManager.eliminar_cliente(self.cliente_id_actual)
                self.limpiar_form()
                self.cargar_grilla()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))
