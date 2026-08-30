from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QTableWidget, 
    QTableWidgetItem, QHeaderView, QLabel
)
from PyQt6.QtCore import Qt
from src.core.productos_manager import ProductosManager
from src.core.promociones_manager import PromocionesManager

class BuscadorProductosDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Buscador de Artículos (F2)")
        self.resize(800, 600)
        self.setStyleSheet("""
            QDialog { background-color: #11111b; color: #cdd6f4; }
            QLineEdit { border: 1px solid #45475a; background-color: #313244; padding: 10px; font-size: 16px; color: #cdd6f4;}
            QTableWidget { background-color: #1e1e2e; color: #cdd6f4; gridline-color: #313244; border: 1px solid #313244;}
            QHeaderView::section { background-color: #181825; color: #cdd6f4; padding: 5px; font-weight: bold; border: none; border-bottom: 1px solid #313244; border-right: 1px solid #313244;}
        """)
        
        self.codigo_seleccionado = None
        self.init_ui()
        self.cargar_grilla()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Buscador
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Buscar:"))
        self.txt_buscar = QLineEdit()
        self.txt_buscar.setPlaceholderText("Escriba nombre, código interno o código de barras...")
        self.txt_buscar.textChanged.connect(self.filtrar_grilla)
        # Seleccionar con flechas
        self.txt_buscar.installEventFilter(self)
        search_layout.addWidget(self.txt_buscar)
        layout.addLayout(search_layout)
        
        # Grilla
        self.tabla = QTableWidget(0, 5)
        self.tabla.setHorizontalHeaderLabels(["Cód. Interno", "Cód. Barras", "Descripción", "P. Contado", "Stock"])
        self.tabla.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.cellDoubleClicked.connect(self.seleccionar_producto)
        self.tabla.installEventFilter(self)
        layout.addWidget(self.tabla)
        
        self.txt_buscar.setFocus()

    def eventFilter(self, source, event):
        if source == self.txt_buscar and event.type() == event.Type.KeyPress:
            if event.key() == Qt.Key.Key_Down:
                self.tabla.setFocus()
                if self.tabla.rowCount() > 0:
                    self.tabla.selectRow(0)
                return True
            elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self.tabla.currentRow() >= 0:
                    self.seleccionar_producto_actual()
                elif self.tabla.rowCount() > 0:
                    self.tabla.selectRow(0)
                    self.seleccionar_producto_actual()
                return True
        elif hasattr(self, 'tabla') and source == self.tabla and event.type() == event.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.seleccionar_producto_actual()
                return True
        return super().eventFilter(source, event)

    def cargar_grilla(self, filtro=""):
        self.tabla.setRowCount(0)
        productos = ProductosManager.get_all()
        for p in productos:
            coincide_nombre = filtro.lower() in p['nombre'].lower()
            coincide_barras = bool(p['codigo_barras'] and filtro in p['codigo_barras'])
            coincide_id = filtro == str(p['id'])
            
            if not (coincide_nombre or coincide_barras or coincide_id):
                continue
            
            row_idx = self.tabla.rowCount()
            self.tabla.insertRow(row_idx)
            
            self.tabla.setItem(row_idx, 0, QTableWidgetItem(str(p['id'])))
            self.tabla.setItem(row_idx, 1, QTableWidgetItem(p['codigo_barras'] or ""))
            self.tabla.setItem(row_idx, 2, QTableWidgetItem(p['nombre']))
            self.tabla.setItem(row_idx, 3, QTableWidgetItem(f"${p['precio_contado']:.2f}"))
            self.tabla.setItem(row_idx, 4, QTableWidgetItem(str(p['stock_actual'])))

        promociones = PromocionesManager.get_all()
        for p in promociones:
            if filtro.lower() not in p['nombre'].lower() and filtro != f"P-{p['id']}":
                continue
            
            row_idx = self.tabla.rowCount()
            self.tabla.insertRow(row_idx)
            
            self.tabla.setItem(row_idx, 0, QTableWidgetItem(f"P-{p['id']}"))
            self.tabla.setItem(row_idx, 1, QTableWidgetItem(""))
            self.tabla.setItem(row_idx, 2, QTableWidgetItem(f"PROMO: {p['nombre']}"))
            self.tabla.setItem(row_idx, 3, QTableWidgetItem(f"${p['precio_fijo']:.2f}"))
            self.tabla.setItem(row_idx, 4, QTableWidgetItem("-"))

    def filtrar_grilla(self, texto):
        self.cargar_grilla(texto)

    def seleccionar_producto_actual(self):
        row = self.tabla.currentRow()
        if row >= 0:
            # Preferir código de barras, si no, usar ID
            cod_barras = self.tabla.item(row, 1).text()
            cod_interno = self.tabla.item(row, 0).text()
            self.codigo_seleccionado = cod_barras if cod_barras else cod_interno
            self.accept()

    def seleccionar_producto(self, row, col):
        cod_barras = self.tabla.item(row, 1).text()
        cod_interno = self.tabla.item(row, 0).text()
        self.codigo_seleccionado = cod_barras if cod_barras else cod_interno
        self.accept()
