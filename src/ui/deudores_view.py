from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QTableWidget, 
    QTableWidgetItem, QPushButton, QHeaderView, QMessageBox, QFrame, QSplitter, QInputDialog, QDialog, QDoubleSpinBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from src.core.clientes_manager import ClientesManager
from src.core.cta_cte_manager import CtaCteManager
from src.core.caja_manager import CajaManager

class DeudoresView(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.cargar_clientes()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        lbl_titulo = QLabel("CUENTAS CORRIENTES (DEUDORES)")
        lbl_titulo.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        lbl_titulo.setStyleSheet("color: #ACE0F4; margin-bottom: 10px;")
        layout.addWidget(lbl_titulo)

        # --- Filtro ---
        filtro_frame = QFrame()
        filtro_frame.setStyleSheet("QFrame { background-color: #1A2026; border-radius: 8px; padding: 10px; }")
        filtro_layout = QHBoxLayout(filtro_frame)
        
        filtro_layout.addWidget(QLabel("Seleccionar Cliente:"))
        self.cb_clientes = QComboBox()
        self.cb_clientes.setMinimumWidth(300)
        self.cb_clientes.currentIndexChanged.connect(self.cargar_datos_cliente)
        filtro_layout.addWidget(self.cb_clientes)
        
        self.btn_recargar = QPushButton("↻ Recargar")
        self.btn_recargar.clicked.connect(self.cargar_clientes)
        filtro_layout.addWidget(self.btn_recargar)
        
        filtro_layout.addStretch()
        layout.addWidget(filtro_frame)

        # --- Resumen ---
        resumen_frame = QFrame()
        resumen_layout = QHBoxLayout(resumen_frame)
        self.lbl_saldo = QLabel("Saldo Pendiente: $0.00")
        self.lbl_saldo.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self.lbl_saldo.setStyleSheet("color: #E28D8D;")
        resumen_layout.addWidget(self.lbl_saldo)
        
        resumen_layout.addStretch()
        
        self.btn_pagar = QPushButton("REGISTRAR PAGO / A FAVOR")
        self.btn_pagar.setStyleSheet("background-color: #8DE2B9; color: #161B22; font-weight: bold; font-size: 16px; padding: 10px 20px;")
        self.btn_pagar.clicked.connect(self.registrar_pago)
        resumen_layout.addWidget(self.btn_pagar)
        layout.addWidget(resumen_frame)

        # --- Historial ---
        self.tabla = QTableWidget(0, 4)
        self.tabla.setHorizontalHeaderLabels(["Fecha", "Tipo", "Detalle", "Monto"])
        self.tabla.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.cellDoubleClicked.connect(self.ver_detalle)
        layout.addWidget(self.tabla)

    def ver_detalle(self, row, col):
        item_fecha = self.tabla.item(row, 0)
        if not item_fecha: return
        venta_id = item_fecha.data(Qt.ItemDataRole.UserRole)
        
        if not venta_id:
            return  # No es una venta (probablemente sea un pago o ajuste)
            
        from src.core.ventas_manager import VentasManager
        try:
            detalles = VentasManager.get_detalles_venta(venta_id)
            texto = f"Detalle de la Venta #{venta_id}:\n\n"
            for d in detalles:
                texto += f"- {d['cantidad']} x {d['nombre']} (${d['precio_unitario']:.2f}) = ${d['subtotal']:.2f}\n"
            
            QMessageBox.information(self, f"Detalle de Compra", texto)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo cargar el detalle:\n{str(e)}")

    def cargar_clientes(self):
        self.cb_clientes.blockSignals(True)
        self.cb_clientes.clear()
        clientes = ClientesManager.get_all()
        for c in clientes:
            if c['id'] != 1: # Ignorar Consumidor Final
                self.cb_clientes.addItem(f"{c['nombre']} (CUIT: {c['cuit']})", c['id'])
        self.cb_clientes.blockSignals(False)
        self.cargar_datos_cliente()

    def cargar_datos_cliente(self):
        cliente_id = self.cb_clientes.currentData()
        if not cliente_id:
            self.lbl_saldo.setText("Saldo Pendiente: $0.00")
            self.tabla.setRowCount(0)
            return
            
        saldo = CtaCteManager.get_saldo(cliente_id)
        if saldo > 0:
            self.lbl_saldo.setText(f"Saldo Pendiente (Deuda): ${saldo:.2f}")
            self.lbl_saldo.setStyleSheet("color: #E28D8D;")
        elif saldo < 0:
            self.lbl_saldo.setText(f"Saldo A Favor: ${abs(saldo):.2f}")
            self.lbl_saldo.setStyleSheet("color: #8DE2B9;")
        else:
            self.lbl_saldo.setText(f"Saldo: $0.00")
            self.lbl_saldo.setStyleSheet("color: #cdd6f4;")
            
        historial = CtaCteManager.get_historial(cliente_id)
        self.tabla.setRowCount(0)
        for h in historial:
            row = self.tabla.rowCount()
            self.tabla.insertRow(row)
            
            item_fecha = QTableWidgetItem(h['fecha'])
            if 'venta_id' in h and h['venta_id']:
                item_fecha.setData(Qt.ItemDataRole.UserRole, h['venta_id'])
            self.tabla.setItem(row, 0, item_fecha)
            
            tipo_item = QTableWidgetItem(h['tipo'])
            if h['tipo'] == 'DEUDA':
                tipo_item.setForeground(Qt.GlobalColor.red)
            else:
                tipo_item.setForeground(Qt.GlobalColor.green)
            self.tabla.setItem(row, 1, tipo_item)
            
            self.tabla.setItem(row, 2, QTableWidgetItem(h['detalle'] or ""))
            self.tabla.setItem(row, 3, QTableWidgetItem(f"${h['monto']:.2f}"))

    def registrar_pago(self):
        cliente_id = self.cb_clientes.currentData()
        if not cliente_id:
            QMessageBox.warning(self, "Atención", "Seleccione un cliente primero.")
            return
            
        saldo = CtaCteManager.get_saldo(cliente_id)
            
        sesion = CajaManager.obtener_sesion_activa()
        if not sesion:
            QMessageBox.critical(self, "Caja Cerrada", "Debe abrir la caja diaria para poder cobrar y que el dinero ingrese a la caja.")
            return

        dialog = PagoDialog(saldo, self)
        if dialog.exec():
            monto, metodo = dialog.get_data()
            try:
                CtaCteManager.registrar_pago(cliente_id, monto, sesion['id'], metodo_pago=metodo)
                QMessageBox.information(self, "Éxito", f"Pago de ${monto:.2f} en {metodo} registrado.")
                self.cargar_datos_cliente()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Ocurrió un error:\n{str(e)}")

class PagoDialog(QDialog):
    def __init__(self, saldo, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Registrar Pago")
        self.setFixedSize(300, 200)
        self.setStyleSheet("QDialog { background-color: #161B22; color: #cdd6f4; } QLabel { color: #cdd6f4; }")
        
        layout = QVBoxLayout(self)
        
        lbl_saldo = QLabel(f"Saldo Total: ${saldo:.2f}")
        lbl_saldo.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        layout.addWidget(lbl_saldo)
        
        layout.addWidget(QLabel("Monto (Abono o Saldo a Favor):"))
        self.spin_monto = QDoubleSpinBox()
        self.spin_monto.setRange(0.01, 10000000.0) # Permitir monto libre, no limitado al saldo
        self.spin_monto.setValue(saldo if saldo > 0 else 0.0)
        self.spin_monto.setDecimals(2)
        self.spin_monto.setStyleSheet("background-color: #32404D; color: #cdd6f4; padding: 5px;")
        layout.addWidget(self.spin_monto)
        
        layout.addWidget(QLabel("Método / Tipo:"))
        self.cb_metodo = QComboBox()
        self.cb_metodo.addItems(["EFECTIVO", "TRANSFERENCIA", "CANJE / MERCADERIA"])
        self.cb_metodo.setStyleSheet("background-color: #32404D; color: #cdd6f4; padding: 5px;")
        layout.addWidget(self.cb_metodo)
        
        btn_layout = QHBoxLayout()
        btn_aceptar = QPushButton("Aceptar")
        btn_aceptar.setStyleSheet("background-color: #8DE2B9; color: #161B22; font-weight: bold; padding: 5px;")
        btn_aceptar.clicked.connect(self.accept)
        
        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.setStyleSheet("background-color: #E28D8D; color: #161B22; font-weight: bold; padding: 5px;")
        btn_cancelar.clicked.connect(self.reject)
        
        btn_layout.addWidget(btn_aceptar)
        btn_layout.addWidget(btn_cancelar)
        layout.addLayout(btn_layout)

    def get_data(self):
        return self.spin_monto.value(), self.cb_metodo.currentText()
