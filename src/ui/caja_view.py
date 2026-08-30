from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QPushButton, QMessageBox, QFrame, QGridLayout, QSpacerItem, QSizePolicy,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from src.core.caja_manager import CajaManager

class CajaView(QWidget):
    def __init__(self):
        super().__init__()
        self.sesion_activa = None
        self.init_ui()
        self.actualizar_estado()

    def crear_tarjeta(self, titulo=None):
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #1E2128;
                border: 1px solid #2A2E38;
                border-radius: 12px;
            }
            QLabel { border: none; }
        """)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        if titulo:
            lbl_titulo = QLabel(titulo)
            lbl_titulo.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
            lbl_titulo.setStyleSheet("color: #ACE0F4;")
            layout.addWidget(lbl_titulo)
            
            linea = QFrame()
            linea.setFrameShape(QFrame.Shape.HLine)
            linea.setStyleSheet("background-color: #2A2E38; border: none; height: 1px;")
            layout.addWidget(linea)
            
        return frame, layout

    def init_ui(self):
        layout_principal = QVBoxLayout(self)
        layout_principal.setContentsMargins(30, 30, 30, 30)
        layout_principal.setSpacing(20)

        # Header
        header_layout = QHBoxLayout()
        lbl_titulo = QLabel("CAJA DIARIA")
        lbl_titulo.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        lbl_titulo.setStyleSheet("color: #E2E8F0;")
        header_layout.addWidget(lbl_titulo)
        
        self.lbl_estado_caja = QLabel("Estado: CERRADA")
        self.lbl_estado_caja.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self.lbl_estado_caja.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        header_layout.addWidget(self.lbl_estado_caja)
        
        layout_principal.addLayout(header_layout)

        # Main Content Layout (Split Left and Right)
        content_layout = QHBoxLayout()
        content_layout.setSpacing(20)

        # --- LEFT PANEL (Apertura y Movimientos) ---
        left_panel = QVBoxLayout()
        left_panel.setSpacing(20)

        # Apertura de Caja
        self.frame_apertura, apertura_layout = self.crear_tarjeta("Apertura de Turno")
        
        form_apertura = QHBoxLayout()
        lbl_monto = QLabel("Monto Inicial en Caja: $")
        lbl_monto.setFont(QFont("Segoe UI", 14))
        lbl_monto.setStyleSheet("color: #A0AEC0;")
        form_apertura.addWidget(lbl_monto)
        
        self.txt_monto_inicial = QLineEdit("0.00")
        self.txt_monto_inicial.setFont(QFont("Segoe UI", 14))
        self.txt_monto_inicial.setFixedWidth(150)
        self.txt_monto_inicial.setStyleSheet("background-color: #16181D; border: 1px solid #32404D; border-radius: 6px; padding: 5px; color: #E2E8F0;")
        form_apertura.addWidget(self.txt_monto_inicial)
        form_apertura.addStretch()
        apertura_layout.addLayout(form_apertura)
        
        self.btn_abrir_caja = QPushButton("ABRIR CAJA")
        self.btn_abrir_caja.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.btn_abrir_caja.setStyleSheet("""
            QPushButton { background-color: #8DE2B9; color: #161B22; border-radius: 6px; padding: 12px; }
            QPushButton:hover { background-color: #A2E8C8; }
        """)
        self.btn_abrir_caja.clicked.connect(self.abrir_caja)
        apertura_layout.addWidget(self.btn_abrir_caja)
        
        left_panel.addWidget(self.frame_apertura)

        # Movimientos Manuales
        self.frame_movimientos, mov_layout = self.crear_tarjeta("Registrar Movimiento")
        
        grid_mov = QGridLayout()
        grid_mov.setSpacing(15)
        
        lbl_tipo = QLabel("Tipo:")
        lbl_tipo.setStyleSheet("color: #A0AEC0; font-size: 14px;")
        grid_mov.addWidget(lbl_tipo, 0, 0)
        
        self.cb_tipo_mov = QComboBox()
        self.cb_tipo_mov.addItems(["INGRESO", "EGRESO"])
        self.cb_tipo_mov.setStyleSheet("background-color: #16181D; border: 1px solid #32404D; border-radius: 6px; padding: 5px; color: #E2E8F0; font-size: 14px;")
        grid_mov.addWidget(self.cb_tipo_mov, 0, 1)

        lbl_monto_mov = QLabel("Monto: $")
        lbl_monto_mov.setStyleSheet("color: #A0AEC0; font-size: 14px;")
        grid_mov.addWidget(lbl_monto_mov, 0, 2)
        
        self.txt_monto_mov = QLineEdit("0.00")
        self.txt_monto_mov.setStyleSheet("background-color: #16181D; border: 1px solid #32404D; border-radius: 6px; padding: 5px; color: #E2E8F0; font-size: 14px;")
        grid_mov.addWidget(self.txt_monto_mov, 0, 3)

        lbl_desc = QLabel("Descripción:")
        lbl_desc.setStyleSheet("color: #A0AEC0; font-size: 14px;")
        grid_mov.addWidget(lbl_desc, 1, 0)
        
        self.txt_desc_mov = QLineEdit()
        self.txt_desc_mov.setPlaceholderText("Ej. Pago a proveedor, Retiro...")
        self.txt_desc_mov.setStyleSheet("background-color: #16181D; border: 1px solid #32404D; border-radius: 6px; padding: 5px; color: #E2E8F0; font-size: 14px;")
        grid_mov.addWidget(self.txt_desc_mov, 1, 1, 1, 3)
        
        mov_layout.addLayout(grid_mov)

        self.btn_registrar_mov = QPushButton("REGISTRAR MOVIMIENTO")
        self.btn_registrar_mov.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.btn_registrar_mov.setStyleSheet("""
            QPushButton { background-color: #ACE0F4; color: #161B22; border-radius: 6px; padding: 12px; }
            QPushButton:hover { background-color: #BDE7F7; }
        """)
        self.btn_registrar_mov.clicked.connect(self.registrar_movimiento)
        mov_layout.addWidget(self.btn_registrar_mov)

        left_panel.addWidget(self.frame_movimientos)
        
        # Tabla de Movimientos de la sesión actual
        self.frame_tabla, tabla_layout = self.crear_tarjeta("Movimientos Registrados")
        self.tabla_movs = QTableWidget(0, 4)
        self.tabla_movs.setHorizontalHeaderLabels(["Fecha", "Tipo", "Descripción", "Monto"])
        self.tabla_movs.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tabla_movs.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tabla_movs.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tabla_movs.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.tabla_movs.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla_movs.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        tabla_layout.addWidget(self.tabla_movs)
        left_panel.addWidget(self.frame_tabla)
        
        left_panel.addStretch()

        content_layout.addLayout(left_panel, 1)

        # --- RIGHT PANEL (Resumen) ---
        self.frame_cierre, cierre_layout = self.crear_tarjeta("Resumen de Caja")
        
        self.grid_resumen = QGridLayout()
        self.grid_resumen.setSpacing(10)
        
        # Diccionario para guardar las referencias a los labels de valores
        self.lbl_valores = {}
        
        campos = [
            ("Saldo Inicial", "monto_inicial", "#A0AEC0"),
            ("Ventas Efectivo", "ventas_efectivo", "#8DE2B9"),
            ("Ventas Transferencia", "ventas_transferencia", "#8DE2B9"),
            ("Ventas Fiadas", "ventas_fiadas", "#F6AD55"),
            ("Cobros Deuda (Evo)", "pagos_deuda_efectivo", "#8DE2B9"),
            ("Cobros Deuda (Trans)", "pagos_deuda_transferencia", "#8DE2B9"),
            ("Ingresos Manuales", "ingresos_manuales", "#8DE2B9"),
            ("Egresos Manuales", "egresos_manuales", "#E28D8D"),
        ]
        
        row = 0
        for titulo, clave, color in campos:
            lbl_tit = QLabel(titulo)
            lbl_tit.setFont(QFont("Segoe UI", 12))
            lbl_tit.setStyleSheet("color: #E2E8F0;")
            
            lbl_val = QLabel("$ 0.00")
            lbl_val.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
            lbl_val.setStyleSheet(f"color: {color};")
            lbl_val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            
            self.grid_resumen.addWidget(lbl_tit, row, 0)
            self.grid_resumen.addWidget(lbl_val, row, 1)
            self.lbl_valores[clave] = lbl_val
            row += 1
            
        # Linea divisoria
        linea_res = QFrame()
        linea_res.setFrameShape(QFrame.Shape.HLine)
        linea_res.setStyleSheet("background-color: #32404D; border: none; height: 1px; margin-top: 10px; margin-bottom: 10px;")
        self.grid_resumen.addWidget(linea_res, row, 0, 1, 2)
        row += 1
        
        # Saldo Efectivo
        lbl_saldo_tit = QLabel("SALDO EFECTIVO CAJA")
        lbl_saldo_tit.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        lbl_saldo_tit.setStyleSheet("color: #E2E8F0;")
        
        self.lbl_saldo_efectivo = QLabel("$ 0.00")
        self.lbl_saldo_efectivo.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        self.lbl_saldo_efectivo.setStyleSheet("color: #8DE2B9;")
        self.lbl_saldo_efectivo.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        self.grid_resumen.addWidget(lbl_saldo_tit, row, 0)
        self.grid_resumen.addWidget(self.lbl_saldo_efectivo, row, 1)
        row += 1
        
        # Total Vendido
        lbl_tot_tit = QLabel("TOTAL VENDIDO")
        lbl_tot_tit.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        lbl_tot_tit.setStyleSheet("color: #A0AEC0;")
        
        self.lbl_total_vendido = QLabel("$ 0.00")
        self.lbl_total_vendido.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self.lbl_total_vendido.setStyleSheet("color: #ACE0F4;")
        self.lbl_total_vendido.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        self.grid_resumen.addWidget(lbl_tot_tit, row, 0)
        self.grid_resumen.addWidget(self.lbl_total_vendido, row, 1)
        
        cierre_layout.addLayout(self.grid_resumen)
        
        cierre_layout.addStretch()
        
        self.btn_cerrar_caja = QPushButton("CERRAR TURNO")
        self.btn_cerrar_caja.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.btn_cerrar_caja.setStyleSheet("""
            QPushButton { background-color: #E28D8D; color: #161B22; border-radius: 8px; padding: 15px; }
            QPushButton:hover { background-color: #E8A2A2; }
            QPushButton:pressed { background-color: #CC7676; }
        """)
        self.btn_cerrar_caja.clicked.connect(self.cerrar_caja)
        cierre_layout.addWidget(self.btn_cerrar_caja)

        content_layout.addWidget(self.frame_cierre, 1)

        layout_principal.addLayout(content_layout)

    def actualizar_estado(self):
        self.sesion_activa = CajaManager.obtener_sesion_activa()
        
        if self.sesion_activa:
            self.lbl_estado_caja.setText(f"● ABIERTA (Inicio: {self.sesion_activa['fecha_apertura']})")
            self.lbl_estado_caja.setStyleSheet("color: #8DE2B9;")
            self.frame_apertura.setVisible(False)
            self.frame_movimientos.setVisible(True)
            self.frame_tabla.setVisible(True)
            self.frame_cierre.setVisible(True)
            self.cargar_resumen()
        else:
            self.lbl_estado_caja.setText("○ CERRADA")
            self.lbl_estado_caja.setStyleSheet("color: #E28D8D;")
            self.frame_apertura.setVisible(True)
            self.frame_movimientos.setVisible(False)
            self.frame_tabla.setVisible(False)
            self.frame_cierre.setVisible(False)

    def abrir_caja(self):
        try:
            monto = float(self.txt_monto_inicial.text())
            CajaManager.abrir_caja(monto)
            self.actualizar_estado()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo abrir la caja:\n{str(e)}")

    def registrar_movimiento(self):
        if not self.sesion_activa:
            return
            
        try:
            tipo = self.cb_tipo_mov.currentText()
            monto = float(self.txt_monto_mov.text())
            desc = self.txt_desc_mov.text().strip()
            
            if monto <= 0:
                QMessageBox.warning(self, "Error", "El monto debe ser mayor a 0.")
                return
            if not desc:
                QMessageBox.warning(self, "Error", "Debe ingresar una descripción.")
                return

            CajaManager.registrar_movimiento(self.sesion_activa['id'], tipo, monto, "EFECTIVO", desc)
            self.txt_monto_mov.setText("0.00")
            self.txt_desc_mov.clear()
            self.cargar_resumen()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Fallo al registrar:\n{str(e)}")

    def cargar_resumen(self):
        if not self.sesion_activa:
            return
            
        resumen = CajaManager.obtener_resumen(self.sesion_activa['id'])
        
        for clave, lbl in self.lbl_valores.items():
            valor = resumen.get(clave, 0.0)
            lbl.setText(f"$ {valor:,.2f}")
            
        self.lbl_saldo_efectivo.setText(f"$ {resumen.get('total_efectivo_esperado', 0.0):,.2f}")
        self.lbl_total_vendido.setText(f"$ {resumen.get('total_vendido', 0.0):,.2f}")
        
        # Cargar tabla de movimientos
        self.tabla_movs.setRowCount(0)
        movimientos = CajaManager.obtener_movimientos(self.sesion_activa['id'])
        for m in movimientos:
            row = self.tabla_movs.rowCount()
            self.tabla_movs.insertRow(row)
            
            self.tabla_movs.setItem(row, 0, QTableWidgetItem(m['fecha']))
            
            item_tipo = QTableWidgetItem(m['tipo'])
            if 'INGRESO' in m['tipo'] or 'VENTA' in m['tipo'] or m['tipo'] == 'PAGO_CTA_CTE':
                item_tipo.setForeground(Qt.GlobalColor.green)
            else:
                item_tipo.setForeground(Qt.GlobalColor.red)
            self.tabla_movs.setItem(row, 1, item_tipo)
            
            self.tabla_movs.setItem(row, 2, QTableWidgetItem(m['descripcion']))
            self.tabla_movs.setItem(row, 3, QTableWidgetItem(f"$ {m['monto']:,.2f}"))

    def cerrar_caja(self):
        if not self.sesion_activa:
            return
            
        reply = QMessageBox.question(self, "Cerrar Caja", "¿Está seguro de cerrar el turno actual?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                resumen = CajaManager.obtener_resumen(self.sesion_activa['id'])
                monto_cierre = resumen['total_efectivo_esperado']
                CajaManager.cerrar_caja(monto_cierre)
                QMessageBox.information(self, "Caja Cerrada", f"Turno cerrado.\n\nSaldo final declarado: ${monto_cierre:,.2f}")
                self.actualizar_estado()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Fallo al cerrar:\n{str(e)}")

    def showEvent(self, event):
        super().showEvent(event)
        self.actualizar_estado()
