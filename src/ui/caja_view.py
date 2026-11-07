from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QPushButton, QMessageBox, QFrame, QGridLayout, QSpacerItem, QSizePolicy,
    QTableWidget, QTableWidgetItem, QHeaderView, QInputDialog
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from src.core.caja_manager import CajaManager, CajaAnteriorError
from src.core.auth_manager import AuthManager

class CajaView(QWidget):
    caja_cerrada = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.sesion_activa = None
        self.init_ui()
        self.actualizar_estado()

    def crear_tarjeta(self, titulo=None):
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
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
            lbl_titulo.setStyleSheet("color: #0284C7;")
            layout.addWidget(lbl_titulo)
            
            linea = QFrame()
            linea.setFrameShape(QFrame.Shape.HLine)
            linea.setStyleSheet("background-color: #E2E8F0; border: none; height: 1px;")
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
        lbl_titulo.setStyleSheet("color: #0F172A;")
        header_layout.addWidget(lbl_titulo)
        
        self.lbl_estado_caja = QLabel("Estado: CERRADA")
        self.lbl_estado_caja.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self.lbl_estado_caja.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        header_layout.addWidget(self.lbl_estado_caja)
        
        layout_principal.addLayout(header_layout)

        self.frame_bloqueo, bloqueo_layout = self.crear_tarjeta("Revisar turno anterior")
        self.lbl_bloqueo = QLabel()
        self.lbl_bloqueo.setWordWrap(True)
        self.lbl_bloqueo.setStyleSheet("font-size: 14px; color: #475569;")
        bloqueo_layout.addWidget(self.lbl_bloqueo)
        self.cb_cajas_anteriores = QComboBox()
        bloqueo_layout.addWidget(self.cb_cajas_anteriores)
        self.btn_cerrar_anterior = QPushButton("Cerrar caja anterior")
        self.btn_cerrar_anterior.clicked.connect(self.cerrar_caja_anterior)
        bloqueo_layout.addWidget(self.btn_cerrar_anterior)
        self.frame_bloqueo.setVisible(False)
        layout_principal.addWidget(self.frame_bloqueo)

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
        lbl_monto.setStyleSheet("color: #475569;")
        form_apertura.addWidget(lbl_monto)
        
        self.txt_monto_inicial = QLineEdit("0.00")
        self.txt_monto_inicial.setFont(QFont("Segoe UI", 14))
        self.txt_monto_inicial.setFixedWidth(150)
        form_apertura.addWidget(self.txt_monto_inicial)
        form_apertura.addStretch()
        apertura_layout.addLayout(form_apertura)
        
        self.btn_abrir_caja = QPushButton("ABRIR CAJA")
        self.btn_abrir_caja.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.btn_abrir_caja.setStyleSheet("""
            QPushButton { background-color: #10B981; color: #FFFFFF; border-radius: 6px; padding: 12px; border: none; }
            QPushButton:hover { background-color: #059669; }
        """)
        self.btn_abrir_caja.clicked.connect(self.abrir_caja)
        apertura_layout.addWidget(self.btn_abrir_caja)
        
        left_panel.addWidget(self.frame_apertura)

        # Movimientos Manuales
        self.frame_movimientos, mov_layout = self.crear_tarjeta("Registrar Movimiento")
        
        grid_mov = QGridLayout()
        grid_mov.setSpacing(15)
        
        lbl_tipo = QLabel("Tipo:")
        lbl_tipo.setStyleSheet("color: #475569; font-size: 14px;")
        grid_mov.addWidget(lbl_tipo, 0, 0)
        
        self.cb_tipo_mov = QComboBox()
        self.cb_tipo_mov.addItems(["INGRESO", "EGRESO"])
        grid_mov.addWidget(self.cb_tipo_mov, 0, 1)

        lbl_monto_mov = QLabel("Monto: $")
        lbl_monto_mov.setStyleSheet("color: #475569; font-size: 14px;")
        grid_mov.addWidget(lbl_monto_mov, 0, 2)
        
        self.txt_monto_mov = QLineEdit("0.00")
        grid_mov.addWidget(self.txt_monto_mov, 0, 3)

        lbl_desc = QLabel("Descripción:")
        lbl_desc.setStyleSheet("color: #475569; font-size: 14px;")
        grid_mov.addWidget(lbl_desc, 1, 0)
        
        self.txt_desc_mov = QLineEdit()
        self.txt_desc_mov.setPlaceholderText("Ej. Pago a proveedor, Retiro...")
        grid_mov.addWidget(self.txt_desc_mov, 1, 1, 1, 3)
        
        mov_layout.addLayout(grid_mov)

        self.btn_registrar_mov = QPushButton("REGISTRAR MOVIMIENTO")
        self.btn_registrar_mov.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.btn_registrar_mov.setStyleSheet("""
            QPushButton { background-color: #0284C7; color: #FFFFFF; border-radius: 6px; padding: 12px; border: none; }
            QPushButton:hover { background-color: #0369A1; }
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
            ("Saldo Inicial", "monto_inicial", "#64748B"),
            ("Ventas Efectivo", "ventas_efectivo", "#10B981"),
            ("Ventas Transferencia", "ventas_transferencia", "#0284C7"),
            ("Ventas Fiadas", "ventas_fiadas", "#D97706"),
            ("Cobros Deuda (Evo)", "pagos_deuda_efectivo", "#10B981"),
            ("Cobros Deuda (Trans)", "pagos_deuda_transferencia", "#0284C7"),
            ("Ingresos Manuales", "ingresos_manuales", "#10B981"),
            ("Egresos Manuales", "egresos_manuales", "#EF4444"),
            ("Pagos a Proveedores (Efectivo)", "pagos_proveedor_efectivo", "#EF4444"),
        ]
        
        row = 0
        for titulo, clave, color in campos:
            lbl_tit = QLabel(titulo)
            lbl_tit.setFont(QFont("Segoe UI", 12))
            lbl_tit.setStyleSheet("color: #334155;")
            
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
        linea_res.setStyleSheet("background-color: #E2E8F0; border: none; height: 1px; margin-top: 10px; margin-bottom: 10px;")
        self.grid_resumen.addWidget(linea_res, row, 0, 1, 2)
        row += 1
        
        # Saldo Efectivo
        lbl_saldo_tit = QLabel("SALDO EFECTIVO CAJA")
        lbl_saldo_tit.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        lbl_saldo_tit.setStyleSheet("color: #0F172A;")
        
        self.lbl_saldo_efectivo = QLabel("$ 0.00")
        self.lbl_saldo_efectivo.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        self.lbl_saldo_efectivo.setStyleSheet("color: #10B981;")
        self.lbl_saldo_efectivo.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        self.grid_resumen.addWidget(lbl_saldo_tit, row, 0)
        self.grid_resumen.addWidget(self.lbl_saldo_efectivo, row, 1)
        row += 1
        
        # Total Vendido
        lbl_tot_tit = QLabel("TOTAL VENDIDO")
        lbl_tot_tit.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        lbl_tot_tit.setStyleSheet("color: #64748B;")
        
        self.lbl_total_vendido = QLabel("$ 0.00")
        self.lbl_total_vendido.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self.lbl_total_vendido.setStyleSheet("color: #0284C7;")
        self.lbl_total_vendido.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        self.grid_resumen.addWidget(lbl_tot_tit, row, 0)
        self.grid_resumen.addWidget(self.lbl_total_vendido, row, 1)
        
        cierre_layout.addLayout(self.grid_resumen)
        
        cierre_layout.addStretch()
        
        self.btn_cerrar_caja = QPushButton("CERRAR TURNO")
        self.btn_cerrar_caja.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.btn_cerrar_caja.setStyleSheet("""
            QPushButton { background-color: #EF4444; color: #FFFFFF; border-radius: 8px; padding: 15px; border: none; }
            QPushButton:hover { background-color: #DC2626; }
            QPushButton:pressed { background-color: #B91C1C; }
        """)
        self.btn_cerrar_caja.clicked.connect(self.cerrar_caja)
        cierre_layout.addWidget(self.btn_cerrar_caja)

        content_layout.addWidget(self.frame_cierre, 1)

        layout_principal.addLayout(content_layout)

    def actualizar_estado(self):
        self.frame_bloqueo.setVisible(False)
        self.cb_cajas_anteriores.clear()
        self.cb_cajas_anteriores.setVisible(False)
        self.btn_cerrar_anterior.setVisible(False)
        try:
            self.sesion_activa = CajaManager.obtener_sesion_activa()
        except Exception as exc:
            self.sesion_activa = None
            self.lbl_estado_caja.setText("REVISIÓN DE TURNO")
            self.lbl_estado_caja.setStyleSheet("color: #B45309;")
            self.frame_apertura.setVisible(False)
            self.frame_movimientos.setVisible(False)
            self.frame_tabla.setVisible(False)
            self.frame_cierre.setVisible(False)
            self.frame_bloqueo.setVisible(True)
            self.lbl_bloqueo.setText(str(exc))
            anteriores = []
            if isinstance(exc, CajaAnteriorError):
                try:
                    anteriores = CajaManager.obtener_cajas_anteriores()
                except Exception:
                    pass
            if anteriores:
                self.lbl_bloqueo.setText(
                    "Hay un turno de una versión anterior sin responsable de apertura registrado. "
                    "Para comenzar un turno nuevo, revise el efectivo y cierre expresamente la caja anterior. "
                    "Se creará un respaldo antes de registrar el cierre. El historial original se conserva; "
                    "este cierre histórico permanecerá local y no se enviará a Supabase."
                )
                for caja in anteriores:
                    self.cb_cajas_anteriores.addItem(
                        f"Turno #{caja['id']} · Apertura: {caja['fecha_apertura']}", caja['id'],
                    )
                self.cb_cajas_anteriores.setVisible(True)
                self.btn_cerrar_anterior.setVisible(True)
            return
        
        if self.sesion_activa:
            responsable = self.sesion_activa.get('responsable_nombre') or 'Sin responsable registrado'
            self.lbl_estado_caja.setText(f"● ABIERTA · {responsable}\nInicio: {self.sesion_activa['fecha_apertura']}")
            self.lbl_estado_caja.setStyleSheet("color: #10B981;")
            self.frame_apertura.setVisible(False)
            self.frame_movimientos.setVisible(True)
            self.frame_tabla.setVisible(True)
            self.frame_cierre.setVisible(True)
            self.cargar_resumen()
        else:
            self.lbl_estado_caja.setText("○ CERRADA")
            self.lbl_estado_caja.setStyleSheet("color: #EF4444;")
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

    def cerrar_caja_anterior(self):
        caja_id = self.cb_cajas_anteriores.currentData()
        if caja_id is None:
            return
        try:
            user = AuthManager.require_user()
            cajas = CajaManager.obtener_cajas_anteriores()
            caja = next((c for c in cajas if c['id'] == caja_id), None)
            if caja is None:
                self.actualizar_estado()
                return
            contado, accepted = QInputDialog.getDouble(
                self, "Contar efectivo de la caja anterior",
                f"Turno #{caja_id}. Ingrese el efectivo realmente contado:",
                0.0, 0.0, 999999999.99, 2,
            )
            if not accepted:
                return
            motivo, accepted = QInputDialog.getMultiLineText(
                self, "Motivo del cierre anterior",
                "Describa el motivo de la regularización (al menos 10 caracteres):", "",
            )
            if not accepted:
                return
            motivo = motivo.strip()
            if len(motivo) < 10:
                QMessageBox.warning(self, "Motivo obligatorio", "Ingrese un motivo de al menos 10 caracteres.")
                return
            esperado = CajaManager.obtener_resumen(caja_id)['total_efectivo_esperado']
            reply = QMessageBox.question(
                self, "Confirmar cierre de caja anterior",
                f"Turno #{caja_id}\nApertura: {caja['fecha_apertura']}\n"
                "Responsable de apertura: No registrado (versión anterior)\n"
                f"Usuario que regulariza: {user.username}\n\n"
                f"Efectivo esperado: ${esperado:,.2f}\nContado: ${contado:,.2f}\n"
                f"Diferencia: ${contado - esperado:,.2f}\nMotivo: {motivo}\n\n"
                "Se creará un respaldo y se registrará este cierre en el historial local. "
                "No se enviará a Supabase. ¿Confirmar?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            cierre = CajaManager.cerrar_caja_anterior(caja_id, contado, motivo)
            self.actualizar_estado()
            QMessageBox.information(
                self, "Caja anterior cerrada",
                f"Turno #{cierre['caja_id']} cerrado por {user.username}.\n"
                f"Contado: ${cierre['contado']:,.2f}\nDiferencia: ${cierre['diferencia']:,.2f}\n\n"
                f"Respaldo previo: {cierre['backup_path']}\n\n"
                "El historial se conserva localmente, sin atribuir un responsable a la apertura anterior. "
                "Si no quedan turnos anteriores abiertos, ya puede abrir un turno nuevo.",
            )
        except Exception as exc:
            QMessageBox.critical(self, "No se pudo cerrar la caja anterior", str(exc))

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
        try:
            user = AuthManager.require_user()
            contado, accepted = QInputDialog.getDouble(
                self, "Contar efectivo", "Ingrese el efectivo realmente contado en caja:",
                0.0, 0.0, 999999999.99, 2,
            )
            if not accepted:
                return
            esperado = CajaManager.obtener_resumen(self.sesion_activa['id'])['total_efectivo_esperado']
            reply = QMessageBox.question(
                self, "Confirmar cierre",
                f"Usuario que cierra: {user.username}\n"
                f"Responsable de apertura: {self.sesion_activa.get('responsable_nombre') or 'Sin registrar'}\n\n"
                f"Efectivo esperado: ${esperado:,.2f}\n"
                f"Efectivo contado: ${contado:,.2f}\n"
                f"Diferencia: ${contado - esperado:,.2f}\n\n¿Registrar el cierre?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            cierre = CajaManager.cerrar_caja(contado)
            self.actualizar_estado()
            self.caja_cerrada.emit()
            QMessageBox.information(
                self, "Caja cerrada",
                f"Cierre registrado por {user.username}.\n"
                f"Contado: ${cierre['monto_cierre']:,.2f}\n"
                f"Diferencia: ${cierre['diferencia']:,.2f}\n\n"
                "El cierre quedó guardado localmente y se enviará cuando haya conexión.",
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Fallo al cerrar:\n{str(e)}")

    def showEvent(self, event):
        super().showEvent(event)
        self.actualizar_estado()
