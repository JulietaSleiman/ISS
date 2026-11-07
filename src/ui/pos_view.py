from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QTableWidget, QTableWidgetItem, QPushButton, QHeaderView, QMessageBox, QFrame, QGridLayout, QInputDialog, QRadioButton, QButtonGroup
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QShortcut, QKeySequence

from src.core.productos_manager import ProductosManager
from src.core.ventas_manager import VentasManager
from src.core.ventas_manager import VentasManager
from src.core.caja_manager import CajaManager
from src.core.promociones_manager import PromocionesManager
from src.core.clientes_manager import ClientesManager
from src.core.cta_cte_manager import CtaCteManager
from src.utils.impresion_ticket import ImpresoraTicket
from src.ui.buscador_productos import BuscadorProductosDialog
from src.ui.buscador_clientes import BuscadorClientesDialog

class POSView(QWidget):
    venta_realizada = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.carrito = [] 
        self.cliente_id_actual = 1
        self.descuento_actual = 0.0
        self._actualizando_tabla = False
        self.init_ui()

    def verificar_caja(self):
        try:
            sesion = CajaManager.obtener_sesion_activa()
        except Exception as exc:
            QMessageBox.warning(self, "Revisar caja", str(exc))
            return False
        if not sesion:
            QMessageBox.warning(self, "Caja Cerrada", "Debe abrir la caja antes de realizar ventas.")
        return bool(sesion)

    def crear_seccion_frame(self):
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
            }
            QLabel { border: none; font-weight: 500; }
        """)
        return frame

    def init_ui(self):
        layout_principal = QVBoxLayout()
        layout_principal.setContentsMargins(20, 20, 20, 20)
        layout_principal.setSpacing(15)
        self.setLayout(layout_principal)

        # --- 1. CABECERA: FACTURACIÓN Y CLIENTE ---
        header_frame = self.crear_seccion_frame()
        header_layout = QGridLayout(header_frame)
        header_layout.setContentsMargins(15, 15, 15, 15)
        header_layout.setVerticalSpacing(10)

        # Fila 0: Info Comprobante y Fecha
        header_layout.addWidget(QLabel("FACTURACIÓN - VENTA"), 0, 0, 1, 2)
        
        # Panel derecho del comprobante (Factura B, etc)
        comprobante_frame = QFrame()
        comprobante_layout = QHBoxLayout(comprobante_frame)
        comprobante_layout.setContentsMargins(0, 0, 0, 0)
        
        cb_tipo_factura = QComboBox()
        cb_tipo_factura.addItems(["Factura B", "Factura A", "Ticket C"])
        cb_tipo_factura.setFixedWidth(100)
        
        lbl_nro_factura = QLabel("Nº 00000001")
        lbl_nro_factura.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        lbl_nro_factura.setStyleSheet("color: #0284C7;")
        
        comprobante_layout.addWidget(cb_tipo_factura)
        comprobante_layout.addWidget(lbl_nro_factura)
        comprobante_layout.addStretch()
        
        comprobante_frame.setVisible(False)
        header_layout.addWidget(comprobante_frame, 0, 4, 1, 2, Qt.AlignmentFlag.AlignRight)

        # Fila 1: Cliente
        header_layout.addWidget(QLabel("Código Cliente:"), 1, 0)
        
        cliente_input_layout = QHBoxLayout()
        self.txt_cod_cliente = QLineEdit("1")
        self.txt_cod_cliente.setFixedWidth(80)
        self.txt_cod_cliente.returnPressed.connect(self.buscar_cliente)
        cliente_input_layout.addWidget(self.txt_cod_cliente)
        
        self.btn_buscar_cliente = QPushButton("(F3)")
        self.btn_buscar_cliente.setStyleSheet("background-color: #F1F5F9; color: #0F172A; border: 1px solid #CBD5E1; padding: 4px; border-radius: 4px; font-weight: bold;")
        self.btn_buscar_cliente.setFixedWidth(50)
        self.btn_buscar_cliente.clicked.connect(self.abrir_buscador_clientes_f3)
        cliente_input_layout.addWidget(self.btn_buscar_cliente)
        
        header_layout.addLayout(cliente_input_layout, 1, 1)

        header_layout.addWidget(QLabel("Nombre:"), 1, 2)
        self.txt_nombre_cliente = QLineEdit("CONSUMIDOR FINAL")
        self.txt_nombre_cliente.setReadOnly(True)
        header_layout.addWidget(self.txt_nombre_cliente, 1, 3, 1, 3)

        # Fila 2: Domicilio, Localidad, Condición
        header_layout.addWidget(QLabel("Domicilio:"), 2, 0)
        self.txt_domicilio = QLineEdit("")
        self.txt_domicilio.setReadOnly(True)
        header_layout.addWidget(self.txt_domicilio, 2, 1, 1, 2)

        header_layout.addWidget(QLabel("Cond. IVA:"), 2, 3)
        self.txt_cond_iva = QLineEdit("Consumidor Final")
        self.txt_cond_iva.setReadOnly(True)
        header_layout.addWidget(self.txt_cond_iva, 2, 4)

        header_layout.addWidget(QLabel("CUIT/DNI:"), 2, 5)
        self.txt_cuit = QLineEdit("00000000000")
        self.txt_cuit.setReadOnly(True)
        header_layout.addWidget(self.txt_cuit, 2, 6)

        layout_principal.addWidget(header_frame)

        # --- 2. INPUT DE PRODUCTO Y TIPO DE CONSUMO ---
        input_layout = QVBoxLayout()
        
        # Tipo de Consumo (Radio Buttons)
        tipo_consumo_layout = QHBoxLayout()
        self.rb_llevar = QRadioButton("Venta Mostrador (Para Llevar)")
        self.rb_local = QRadioButton("Consumir en Local (Mesa)")
        self.rb_llevar.setChecked(True) # Por defecto
        
        # Estilos para que se vean bien
        estilo_rb = "QRadioButton { font-size: 15px; font-weight: bold; color: #0284C7; padding: 5px; }"
        self.rb_llevar.setStyleSheet(estilo_rb)
        self.rb_local.setStyleSheet(estilo_rb)
        
        self.bg_consumo = QButtonGroup()
        self.bg_consumo.addButton(self.rb_llevar)
        self.bg_consumo.addButton(self.rb_local)
        
        tipo_consumo_layout.addWidget(self.rb_llevar)
        tipo_consumo_layout.addWidget(self.rb_local)
        tipo_consumo_layout.addStretch()
        
        self.rb_llevar.toggled.connect(self.actualizar_precios_carrito)
        self.rb_local.toggled.connect(self.actualizar_precios_carrito)
        
        input_layout.addLayout(tipo_consumo_layout)
        
        # Buscador
        search_bar_layout = QHBoxLayout()
        self.txt_codigo = QLineEdit()
        self.txt_codigo.setFont(QFont("Segoe UI", 16))
        self.txt_codigo.setPlaceholderText("Ingrese Código de Barras o Artículo y presione Enter (F2 para buscar)...")
        self.txt_codigo.setMinimumHeight(50)
        self.txt_codigo.returnPressed.connect(self.buscar_y_agregar_producto)
        search_bar_layout.addWidget(self.txt_codigo)
        
        input_layout.addLayout(search_bar_layout)
        layout_principal.addLayout(input_layout)

        # --- 3. GRILLA DE PRODUCTOS ---
        self.tabla_carrito = QTableWidget(0, 5)
        self.tabla_carrito.setHorizontalHeaderLabels(["Código", "Descripción", "Cantidad", "P. Unitario", "Importe"])
        self.tabla_carrito.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tabla_carrito.setFont(QFont("Segoe UI", 12))
        self.tabla_carrito.verticalHeader().setVisible(False)
        self.tabla_carrito.verticalHeader().setDefaultSectionSize(40)
        self.tabla_carrito.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla_carrito.itemChanged.connect(self.al_cambiar_celda)
        layout_principal.addWidget(self.tabla_carrito)

        # --- 4. PANEL INFERIOR: TOTALES Y ACCIONES ---
        bottom_frame = self.crear_seccion_frame()
        bottom_layout = QHBoxLayout(bottom_frame)
        bottom_layout.setContentsMargins(15, 15, 15, 15)

        # Vendedor e Info adicional
        info_layout = QVBoxLayout()
        info_layout.addWidget(QLabel("Vendedor: 01 - Principal"))
        lbl_shortcuts = QLabel("[F5] Cobrar   |   [F12] Cancelar Venta   |   [Supr] Eliminar Fila")
        lbl_shortcuts.setStyleSheet("color: #64748B;")
        info_layout.addWidget(lbl_shortcuts)
        bottom_layout.addLayout(info_layout)

        bottom_layout.addStretch()

        # Botones de Acción
        self.btn_cobrar = QPushButton("COBRAR (F5)")
        self.btn_cobrar.setMinimumSize(150, 60)
        self.btn_cobrar.setStyleSheet("""
            QPushButton { background-color: #10B981; color: #FFFFFF; font-weight: bold; font-size: 16px; border-radius: 8px; border: none;}
            QPushButton:hover { background-color: #059669; }
            QPushButton:pressed { background-color: #047857; }
        """)
        self.btn_cobrar.clicked.connect(self.cobrar_venta)

        self.btn_cancelar = QPushButton("CANCELAR (F12)")
        self.btn_cancelar.setMinimumSize(150, 60)
        self.btn_cancelar.setStyleSheet("""
            QPushButton { background-color: #EF4444; color: #FFFFFF; font-weight: bold; font-size: 16px; border-radius: 8px; border: none;}
            QPushButton:hover { background-color: #DC2626; }
            QPushButton:pressed { background-color: #B91C1C; }
        """)
        self.btn_cancelar.clicked.connect(self.cancelar_venta)

        bottom_layout.addWidget(self.btn_cobrar)
        bottom_layout.addWidget(self.btn_cancelar)
        
        # Separador / Espacio
        bottom_layout.addStretch()

        # Selector de Medio de Pago
        pago_layout = QVBoxLayout()
        pago_layout.addWidget(QLabel("Medio de Pago:"))
        self.cb_medio_pago = QComboBox()
        self.cb_medio_pago.addItems(["EFECTIVO", "TRANSFERENCIA", "MIXTO", "FIADO / CTA. CTE."])
        self.cb_medio_pago.setStyleSheet("font-size: 16px; font-weight: bold; padding: 5px;")
        self.cb_medio_pago.setFixedHeight(40)
        pago_layout.addWidget(self.cb_medio_pago)
        pago_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        bottom_layout.addLayout(pago_layout)

        # Contenedor para el total
        total_layout = QVBoxLayout()
        
        self.lbl_descuento = QLabel("")
        self.lbl_descuento.setFont(QFont("Segoe UI", 12))
        self.lbl_descuento.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
        self.lbl_descuento.setStyleSheet("color: #EF4444;")
        
        self.lbl_total = QLabel("$0.00")
        self.lbl_total.setFont(QFont("Segoe UI", 48, QFont.Weight.Bold))
        self.lbl_total.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        self.lbl_total.setStyleSheet("color: #0284C7;")
        
        total_layout.addWidget(self.lbl_descuento)
        total_layout.addWidget(self.lbl_total)
        
        bottom_layout.addLayout(total_layout)

        layout_principal.addWidget(bottom_frame)

        # --- Atajos ---
        QShortcut(QKeySequence("F5"), self, self.cobrar_venta)
        QShortcut(QKeySequence("F12"), self, self.cancelar_venta)
        QShortcut(QKeySequence("F2"), self, self.abrir_buscador_f2)
        QShortcut(QKeySequence("F3"), self, self.abrir_buscador_clientes_f3)
        QShortcut(QKeySequence("Delete"), self, self.eliminar_fila)

        self.txt_codigo.setFocus()

    def eliminar_fila(self):
        row = self.tabla_carrito.currentRow()
        if row >= 0:
            del self.carrito[row]
            self.procesar_promociones()
            self.actualizar_tabla()
            self.txt_codigo.setFocus()

    def abrir_buscador_f2(self):
        dialog = BuscadorProductosDialog(self)
        if dialog.exec():
            if dialog.codigo_seleccionado:
                self.txt_codigo.setText(dialog.codigo_seleccionado)
                self.buscar_y_agregar_producto()
        self.txt_codigo.setFocus()

    def abrir_buscador_clientes_f3(self):
        dialog = BuscadorClientesDialog(self)
        if dialog.exec():
            if dialog.cliente_id_seleccionado:
                self.txt_cod_cliente.setText(str(dialog.cliente_id_seleccionado))
                self.buscar_cliente()
        self.txt_codigo.setFocus()

    def buscar_cliente(self):
        try:
            cod_cliente = int(self.txt_cod_cliente.text().strip())
        except ValueError:
            QMessageBox.warning(self, "Error", "El código de cliente debe ser numérico.")
            self.txt_cod_cliente.setText(str(self.cliente_id_actual))
            return

        cliente = ClientesManager.get_by_id(cod_cliente)
        if cliente:
            self.cliente_id_actual = cliente['id']
            self.descuento_actual = cliente.get('descuento_porcentaje', 0.0)
            
            saldo = CtaCteManager.get_saldo(cliente['id'])
            if saldo < 0:
                self.txt_nombre_cliente.setText(f"{cliente['nombre']} (A favor: ${abs(saldo):.2f})")
            else:
                self.txt_nombre_cliente.setText(cliente['nombre'])
                
            self.txt_domicilio.setText(cliente['domicilio'])
            self.txt_cond_iva.setText(cliente['condicion_iva'])
            self.txt_cuit.setText(cliente['cuit'])
            self.txt_codigo.setFocus()
            self.actualizar_tabla()
        else:
            QMessageBox.warning(self, "No Encontrado", f"No se encontró un cliente con el código {cod_cliente}.")
            # Restaurar al último cliente válido
            self.txt_cod_cliente.setText(str(self.cliente_id_actual))
            self.actualizar_tabla()

    def buscar_y_agregar_producto(self):
        codigo = self.txt_codigo.text().strip()
        if not codigo:
            return

        if codigo.startswith("P-"):
            try:
                promo_id = int(codigo.split("-")[1])
                promos = PromocionesManager.get_all()
                promo = next((p for p in promos if p['id'] == promo_id), None)
                if promo:
                    encontrada = False
                    for item in self.carrito:
                        if item.get('es_promo') and item['promocion_id'] == promo['id']:
                            item['cantidad'] += 1
                            encontrada = True
                            break
                    if not encontrada:
                        self.carrito.append({
                            'producto_id': None,
                            'promocion_id': promo['id'],
                            'codigo_barras': '[COMBO]',
                            'nombre': "PROMO: " + promo['nombre'],
                            'cantidad': 1,
                            'precio_unitario': promo['precio_fijo'],
                            'es_promo': True,
                            'detalles': promo['detalles']
                        })
                    self.procesar_promociones()
                    self.actualizar_tabla()
                    self.txt_codigo.clear()
                    self.txt_codigo.setFocus()
                    return
            except ValueError:
                pass

        producto = ProductosManager.get_by_codigo(codigo)
        if not producto:
            QMessageBox.warning(self, "No Encontrado", f"Artículo no encontrado: {codigo}")
            self.txt_codigo.clear()
            return

        # Determinar el precio según tipo de consumo
        if self.rb_local.isChecked() and producto['precio_tarjeta'] is not None and float(producto['precio_tarjeta']) > 0:
            precio_a_cobrar = float(producto['precio_tarjeta']) # Precio Local
        else:
            precio_a_cobrar = float(producto['precio_contado']) # Precio Mostrador
        
        # Verificar si ya está en el carrito para sumar cantidad (y chequear que sea el mismo precio)
        encontrado = False
        for item in self.carrito:
            if item['producto_id'] == producto['id'] and item['precio_unitario'] == precio_a_cobrar:
                item['cantidad'] += 1
                encontrado = True
                break
        
        if not encontrado:
            self.carrito.append({
                'producto_id': producto['id'],
                'codigo_barras': producto['codigo_barras'],
                'nombre': producto['nombre'],
                'cantidad': 1,
                'precio_unitario': precio_a_cobrar,
                'es_promo': False
            })

        self.procesar_promociones()
        self.actualizar_tabla()
        self.txt_codigo.clear()
        self.txt_codigo.setFocus()

    def actualizar_precios_carrito(self):
        for item in self.carrito:
            if item.get('es_promo'):
                continue
                
            producto = ProductosManager.get_by_id(item['producto_id'])
            if not producto:
                continue
                
            if self.rb_local.isChecked() and producto['precio_tarjeta'] is not None and float(producto['precio_tarjeta']) > 0:
                item['precio_unitario'] = float(producto['precio_tarjeta'])
            else:
                item['precio_unitario'] = float(producto['precio_contado'])
                
        self.procesar_promociones()
        self.actualizar_tabla()
        self.txt_codigo.setFocus()

    def procesar_promociones(self):
        promos = PromocionesManager.get_all()
        if not promos:
            return

        cambio = True
        while cambio:
            cambio = False
            for promo in promos:
                # Verificar si tenemos los items requeridos
                cumple_promo = True
                items_a_consumir = []
                
                for det in promo['detalles']:
                    req_id = det['producto_id']
                    req_cant = det['cantidad_requerida']
                    
                    # Buscar en el carrito
                    cant_en_carrito = 0
                    for item in self.carrito:
                        if not item.get('es_promo') and item['producto_id'] == req_id:
                            cant_en_carrito += item['cantidad']
                    
                    if cant_en_carrito < req_cant:
                        cumple_promo = False
                        break
                    else:
                        items_a_consumir.append({'id': req_id, 'cant': req_cant})
                
                if cumple_promo:
                    # Aplicar promo
                    cambio = True
                    # Restar cantidades
                    for cons in items_a_consumir:
                        cant_a_restar = cons['cant']
                        for item in self.carrito:
                            if not item.get('es_promo') and item['producto_id'] == cons['id']:
                                if item['cantidad'] >= cant_a_restar:
                                    item['cantidad'] -= cant_a_restar
                                    cant_a_restar = 0
                                else:
                                    cant_a_restar -= item['cantidad']
                                    item['cantidad'] = 0
                                if cant_a_restar == 0:
                                    break
                    
                    # Limpiar items con cantidad 0
                    self.carrito = [item for item in self.carrito if item['cantidad'] > 0]
                    
                    # Verificar si la promo ya existe para sumar cantidad
                    encontrada = False
                    for item in self.carrito:
                        if item.get('es_promo') and item['nombre'] == "PROMO: " + promo['nombre']:
                            item['cantidad'] += 1
                            encontrada = True
                            break
                            
                    if not encontrada:
                        self.carrito.append({
                            'producto_id': None,
                            'promocion_id': promo['id'],
                            'codigo_barras': '[COMBO]',
                            'nombre': "PROMO: " + promo['nombre'],
                            'cantidad': 1,
                            'precio_unitario': promo['precio_fijo'],
                            'es_promo': True,
                            'detalles': promo['detalles']
                        })
                    break # Restart loop since cart changed

    def actualizar_tabla(self):
        self._actualizando_tabla = True
        self.tabla_carrito.setRowCount(0)
        total = 0.0
        for item in self.carrito:
            row_idx = self.tabla_carrito.rowCount()
            self.tabla_carrito.insertRow(row_idx)
            
            subtotal = item['cantidad'] * item['precio_unitario']
            total += subtotal

            # Crear items
            item_cod = QTableWidgetItem(item['codigo_barras'])
            item_desc = QTableWidgetItem(item['nombre'])
            item_cant = QTableWidgetItem(f"{item['cantidad']:g}")
            item_pu = QTableWidgetItem(f"{item['precio_unitario']:.2f}")
            item_imp = QTableWidgetItem(f"{subtotal:.2f}")

            # Solo la cantidad (columna 2) es editable, el resto bloqueado
            item_cod.setFlags(item_cod.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item_desc.setFlags(item_desc.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if item.get('es_promo'):
                item_cant.setFlags(item_cant.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item_pu.setFlags(item_pu.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item_imp.setFlags(item_imp.flags() & ~Qt.ItemFlag.ItemIsEditable)

            self.tabla_carrito.setItem(row_idx, 0, item_cod)
            self.tabla_carrito.setItem(row_idx, 1, item_desc)
            self.tabla_carrito.setItem(row_idx, 2, item_cant)
            self.tabla_carrito.setItem(row_idx, 3, item_pu)
            self.tabla_carrito.setItem(row_idx, 4, item_imp)

        if self.descuento_actual > 0:
            descuento_monto = total * (self.descuento_actual / 100.0)
            total_final = total - descuento_monto
            self.lbl_descuento.setText(f"Subtotal: ${total:.2f} | Descuento {self.descuento_actual:.0f}%: -${descuento_monto:.2f}")
            self.lbl_total.setText(f"${total_final:.2f}")
        else:
            self.lbl_descuento.setText("")
            self.lbl_total.setText(f"${total:.2f}")
        self._actualizando_tabla = False

    def al_cambiar_celda(self, item):
        if self._actualizando_tabla:
            return
            
        row = item.row()
        col = item.column()
        
        if col == 2: # Columna Cantidad
            try:
                texto_cant = item.text().replace(',', '.')
                nueva_cantidad = float(texto_cant)
                if nueva_cantidad <= 0:
                    raise ValueError
            except ValueError:
                QMessageBox.warning(self, "Error", "La cantidad debe ser un número mayor a 0.")
                self.actualizar_tabla()
                return

            if row < len(self.carrito):
                self.carrito[row]['cantidad'] = nueva_cantidad
                self.procesar_promociones()
                self.actualizar_tabla()

    def resetear_estado_venta(self):
        self.carrito.clear()
        self.txt_cod_cliente.setText("1")
        self.buscar_cliente()
        self.cb_medio_pago.setCurrentText("EFECTIVO")
        self.txt_codigo.clear()
        self.txt_codigo.setFocus()

    def cancelar_venta(self):
        if self.carrito:
            reply = QMessageBox.question(self, "Cancelar Venta", "¿Está seguro de cancelar la venta actual?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.resetear_estado_venta()
        else:
            self.resetear_estado_venta()
        self.txt_codigo.setFocus()

    def cobrar_venta(self):
        if not self.carrito:
            QMessageBox.warning(self, "Vacio", "No hay artículos para cobrar.")
            self.txt_codigo.setFocus()
            return

        try:
            metodo_pago_seleccionado = self.cb_medio_pago.currentText()

            if metodo_pago_seleccionado == "FIADO / CTA. CTE." and self.cliente_id_actual == 1:
                QMessageBox.warning(self, "Error", "No se puede fiar al 'Consumidor Final'. Debe seleccionar o crear un Cliente específico.")
                return

            total_venta = 0.0
            for item in self.carrito:
                total_venta += item['cantidad'] * item['precio_unitario']
            descuento_monto = total_venta * (self.descuento_actual / 100.0)
            total_final = total_venta - descuento_monto
            
            if metodo_pago_seleccionado == "EFECTIVO":
                pago, ok = QInputDialog.getDouble(
                    self, 
                    "Cobro en Efectivo", 
                    f"Total a cobrar: ${total_final:.2f}\n\n¿Cuánto efectivo entrega el cliente?", 
                    total_final, 0.0, 10000000.0, 2
                )
                if not ok:
                    return # Canceló el cobro
                if pago < total_final:
                    QMessageBox.warning(self, "Error", f"El monto entregado (${pago:.2f}) es menor al total de la venta (${total_final:.2f}).")
                    return
                vuelto = pago - total_final
                montos_mixto = None

            elif metodo_pago_seleccionado == "MIXTO":
                # Pedimos la parte en Efectivo
                monto_efectivo, ok = QInputDialog.getDouble(
                    self, 
                    "Cobro Mixto", 
                    f"Total a cobrar: ${total_final:.2f}\n\n¿Cuánto entrega en EFECTIVO? (El resto será TRANSFERENCIA)", 
                    0.0, 0.0, total_final, 2
                )
                if not ok:
                    return # Canceló el cobro
                
                monto_transferencia = total_final - monto_efectivo
                montos_mixto = {
                    'EFECTIVO': monto_efectivo,
                    'TRANSFERENCIA': monto_transferencia
                }
                vuelto = 0.0

            else:
                montos_mixto = None
                vuelto = 0.0
                
            resultado = VentasManager.procesar_venta(
                cliente_id=self.cliente_id_actual,
                metodo_pago=metodo_pago_seleccionado,
                carrito=self.carrito,
                montos_mixto=montos_mixto
            )
            
            ImpresoraTicket.imprimir(
                venta_id=resultado["venta_id"],
                carrito=self.carrito,
                subtotal=resultado["subtotal"],
                descuento=resultado["descuento"],
                total=resultado["total"],
                empresa_nombre="BEBIDAS FRIAS"
            )
            
            if metodo_pago_seleccionado == "EFECTIVO":
                QMessageBox.information(self, "Venta Exitosa", f"Vuelto a entregar: ${vuelto:.2f}\n\nFactura #{resultado['venta_id']} generada.\nImprimiendo...")
            else:
                QMessageBox.information(self, "Venta Exitosa", f"Factura #{resultado['venta_id']} generada.\nImprimiendo...")
                
            self.resetear_estado_venta()
            self.venta_realizada.emit()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Fallo al procesar:\n{str(e)}")
        
        self.txt_codigo.setFocus()
