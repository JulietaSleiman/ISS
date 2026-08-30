from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QTableWidget, QTableWidgetItem, QPushButton, QHeaderView, QMessageBox, QFrame, QGridLayout, QSplitter, QCheckBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QShortcut, QKeySequence

class NumericLineEdit(QLineEdit):
    def focusInEvent(self, event):
        super().focusInEvent(event)
        QTimer.singleShot(0, self.selectAll)

from src.core.productos_manager import ProductosManager
from src.core.categorias_manager import CategoriasManager
from src.core.proveedores_manager import ProveedoresManager

class ProductosView(QWidget):
    def __init__(self):
        super().__init__()
        self.producto_seleccionado_id = None
        self.init_ui()
        self.cargar_combos()
        self.cargar_grilla()

    def crear_seccion_frame(self):
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #1A2026;
                border: 1px solid #32404D;
                border-radius: 8px;
            }
            QLabel { border: none; font-weight: 500; font-size: 14px; }
        """)
        return frame

    def cargar_combos(self):
        # Guardar selecciones actuales
        cur_cat = self.cb_categoria.currentData() if hasattr(self, 'cb_categoria') else None
        cur_prov = self.cb_proveedor.currentData() if hasattr(self, 'cb_proveedor') else None
        cur_filtro_cat = self.cb_filtro_categoria.currentData() if hasattr(self, 'cb_filtro_categoria') else None
        cur_filtro_prov = self.cb_filtro_proveedor.currentData() if hasattr(self, 'cb_filtro_proveedor') else None

        cats = CategoriasManager.get_all()
        provs = ProveedoresManager.get_all()

        if hasattr(self, 'cb_categoria'):
            self.cb_categoria.blockSignals(True)
            self.cb_categoria.clear()
            self.cb_categoria.addItem("-- Ninguno --", None)
            for c in cats:
                self.cb_categoria.addItem(c['nombre'], c['id'])
            if cur_cat is not None:
                idx = self.cb_categoria.findData(cur_cat)
                if idx >= 0: self.cb_categoria.setCurrentIndex(idx)
            self.cb_categoria.blockSignals(False)
            
        if hasattr(self, 'cb_proveedor'):
            self.cb_proveedor.blockSignals(True)
            self.cb_proveedor.clear()
            self.cb_proveedor.addItem("-- Ninguno --", None)
            for p in provs:
                self.cb_proveedor.addItem(p['nombre'], p['id'])
            if cur_prov is not None:
                idx = self.cb_proveedor.findData(cur_prov)
                if idx >= 0: self.cb_proveedor.setCurrentIndex(idx)
            self.cb_proveedor.blockSignals(False)

        if hasattr(self, 'cb_filtro_categoria'):
            self.cb_filtro_categoria.blockSignals(True)
            self.cb_filtro_categoria.clear()
            self.cb_filtro_categoria.addItem("Todos", None)
            for c in cats:
                self.cb_filtro_categoria.addItem(c['nombre'], c['id'])
            if cur_filtro_cat is not None:
                idx = self.cb_filtro_categoria.findData(cur_filtro_cat)
                if idx >= 0: self.cb_filtro_categoria.setCurrentIndex(idx)
            self.cb_filtro_categoria.blockSignals(False)
            
        if hasattr(self, 'cb_filtro_proveedor'):
            self.cb_filtro_proveedor.blockSignals(True)
            self.cb_filtro_proveedor.clear()
            self.cb_filtro_proveedor.addItem("Todos", None)
            for p in provs:
                self.cb_filtro_proveedor.addItem(p['nombre'], p['id'])
            if cur_filtro_prov is not None:
                idx = self.cb_filtro_proveedor.findData(cur_filtro_prov)
                if idx >= 0: self.cb_filtro_proveedor.setCurrentIndex(idx)
            self.cb_filtro_proveedor.blockSignals(False)

    def init_ui(self):
        layout_principal = QVBoxLayout()
        layout_principal.setContentsMargins(20, 20, 20, 20)
        layout_principal.setSpacing(15)
        self.setLayout(layout_principal)

        lbl_titulo = QLabel("MANTENIMIENTO DE ARTÍCULOS")
        lbl_titulo.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        lbl_titulo.setStyleSheet("color: #ACE0F4;")
        layout_principal.addWidget(lbl_titulo)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # --- PANEL SUPERIOR: FORMULARIO ---
        form_widget = QWidget()
        form_layout = QVBoxLayout(form_widget)
        form_layout.setContentsMargins(0,0,0,0)

        # Bloque 1: Generales
        g_frame = self.crear_seccion_frame()
        g_layout = QGridLayout(g_frame)
        
        g_layout.addWidget(QLabel("Cód. Interno:"), 0, 0)
        self.txt_codigo_interno = QLineEdit("[ Automático ]")
        self.txt_codigo_interno.setReadOnly(True)
        self.txt_codigo_interno.setStyleSheet("color: #9EB3C2; background-color: transparent; border: none;")
        g_layout.addWidget(self.txt_codigo_interno, 0, 1)

        g_layout.addWidget(QLabel("Cód. Barras (Opcional):"), 0, 2)
        self.txt_codigo_barras = QLineEdit()
        g_layout.addWidget(self.txt_codigo_barras, 0, 3)

        g_layout.addWidget(QLabel("Descripción:"), 0, 4)
        self.txt_descripcion = QLineEdit()
        g_layout.addWidget(self.txt_descripcion, 0, 5, 1, 2)

        g_layout.addWidget(QLabel("Cód. Fábrica:"), 1, 0)
        self.txt_codigo_fabrica = QLineEdit()
        g_layout.addWidget(self.txt_codigo_fabrica, 1, 1)

        g_layout.addWidget(QLabel("Rubro/Categoría:"), 1, 2)
        self.cb_categoria = QComboBox()
        g_layout.addWidget(self.cb_categoria, 1, 3)

        g_layout.addWidget(QLabel("Proveedor:"), 1, 4)
        self.cb_proveedor = QComboBox()
        g_layout.addWidget(self.cb_proveedor, 1, 5, 1, 2)

        form_layout.addWidget(g_frame)

        # Bloque 2: Precios y Costos
        p_frame = self.crear_seccion_frame()
        p_layout = QGridLayout(p_frame)

        p_layout.addWidget(QLabel("Costo Lista:"), 0, 0)
        self.txt_costo_lista = NumericLineEdit("0.00")
        p_layout.addWidget(self.txt_costo_lista, 0, 1)

        p_layout.addWidget(QLabel("Flete/Varios:"), 0, 2)
        self.txt_flete = NumericLineEdit("0.00")
        p_layout.addWidget(self.txt_flete, 0, 3)

        p_layout.addWidget(QLabel("Utilidad (%):"), 1, 0)
        self.txt_utilidad = NumericLineEdit("0.00")
        p_layout.addWidget(self.txt_utilidad, 1, 1)

        p_layout.addWidget(QLabel("Precio Mostrador:"), 1, 2)
        self.txt_precio_contado = NumericLineEdit("0.00")
        self.txt_precio_contado.setStyleSheet("background-color: #1A2026; font-weight: bold; color: #8DE2B9; font-size: 16px;")
        p_layout.addWidget(self.txt_precio_contado, 1, 3)

        p_layout.addWidget(QLabel("Precio Local:"), 1, 4)
        self.txt_precio_tarjeta = NumericLineEdit("0.00")
        self.txt_precio_tarjeta.setStyleSheet("background-color: #1A2026; font-weight: bold; color: #ACE0F4; font-size: 16px;")
        p_layout.addWidget(self.txt_precio_tarjeta, 1, 5)

        form_layout.addWidget(p_frame)

        # Conectar señales para cálculos dinámicos
        self.txt_costo_lista.textEdited.connect(self.calcular_precios_desde_costo)
        self.txt_flete.textEdited.connect(self.calcular_precios_desde_costo)
        self.txt_utilidad.textEdited.connect(self.calcular_precios_desde_costo)
        self.txt_precio_contado.textEdited.connect(self.calcular_utilidad_desde_precio)

        # Bloque 3: Stock y Observaciones
        s_frame = self.crear_seccion_frame()
        s_layout = QGridLayout(s_frame)

        s_layout.addWidget(QLabel("Stock Mínimo:"), 0, 0)
        self.txt_stock_min = NumericLineEdit("5")
        s_layout.addWidget(self.txt_stock_min, 0, 1)

        s_layout.addWidget(QLabel("Stock Actual:"), 0, 2)
        self.txt_stock_actual = NumericLineEdit("0")
        s_layout.addWidget(self.txt_stock_actual, 0, 3)

        s_layout.addWidget(QLabel("Stock Máximo:"), 1, 0)
        self.txt_stock_max = NumericLineEdit("100")
        s_layout.addWidget(self.txt_stock_max, 1, 1)

        s_layout.addWidget(QLabel("Ubicación:"), 1, 2)
        self.txt_ubicacion = QLineEdit("")
        s_layout.addWidget(self.txt_ubicacion, 1, 3)

        form_layout.addWidget(s_frame)

        # --- BOTONES DE ACCIÓN ---
        btn_layout = QHBoxLayout()
        
        self.btn_limpiar = QPushButton("Limpiar/Nuevo")
        self.btn_limpiar.clicked.connect(self.limpiar_formulario)
        
        self.btn_eliminar = QPushButton("Eliminar")
        self.btn_eliminar.setStyleSheet("background-color: #E28D8D; color: #161B22; font-weight: bold; border: none;")
        self.btn_eliminar.clicked.connect(self.eliminar_producto)
        self.btn_eliminar.setEnabled(False)

        self.btn_restaurar = QPushButton("Restaurar")
        self.btn_restaurar.setStyleSheet("background-color: #8DE2B9; color: #161B22; font-weight: bold; border: none;")
        self.btn_restaurar.clicked.connect(self.restaurar_producto)
        self.btn_restaurar.setVisible(False)

        self.btn_ficha = QPushButton("Ver Ficha")
        self.btn_ficha.setStyleSheet("background-color: #ACE0F4; color: #161B22; font-weight: bold; border: none;")
        self.btn_ficha.clicked.connect(self.ver_ficha_producto)
        self.btn_ficha.setEnabled(False)

        self.btn_grabar = QPushButton("Guardar (F5)")
        self.btn_grabar.setStyleSheet("background-color: #8DE2B9; color: #161B22; font-weight: bold; border: none;")
        self.btn_grabar.clicked.connect(self.grabar_producto)
        
        self.shortcut_f5 = QShortcut(QKeySequence("F5"), self)
        self.shortcut_f5.activated.connect(self.grabar_producto)
        self.shortcut_f5.setContext(Qt.ShortcutContext.WindowShortcut)
        
        self.btn_duplicar = QPushButton("Duplicar")
        self.btn_duplicar.setStyleSheet("background-color: #D3C6AA; color: #161B22; font-weight: bold; border: none;")
        self.btn_duplicar.clicked.connect(self.duplicar_producto)

        btn_layout.addWidget(self.btn_limpiar)
        btn_layout.addWidget(self.btn_eliminar)
        btn_layout.addWidget(self.btn_restaurar)
        btn_layout.addWidget(self.btn_ficha)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_duplicar)
        btn_layout.addWidget(self.btn_grabar)

        form_layout.addLayout(btn_layout)
        
        splitter.addWidget(form_widget)

        # --- PANEL INFERIOR: GRILLA ---
        grid_widget = QWidget()
        grid_layout = QVBoxLayout(grid_widget)
        grid_layout.setContentsMargins(0,0,0,0)

        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Búsqueda Rápida:"))
        self.txt_buscar = QLineEdit()
        self.txt_buscar.setPlaceholderText("Nombre, Código o ID...")
        self.txt_buscar.textChanged.connect(self.filtrar_grilla)
        search_layout.addWidget(self.txt_buscar)
        
        search_layout.addWidget(QLabel("Rubro:"))
        self.cb_filtro_categoria = QComboBox()
        self.cb_filtro_categoria.currentIndexChanged.connect(lambda _: self.filtrar_grilla(self.txt_buscar.text()))
        search_layout.addWidget(self.cb_filtro_categoria)

        search_layout.addWidget(QLabel("Proveedor:"))
        self.cb_filtro_proveedor = QComboBox()
        self.cb_filtro_proveedor.currentIndexChanged.connect(lambda _: self.filtrar_grilla(self.txt_buscar.text()))
        search_layout.addWidget(self.cb_filtro_proveedor)
        
        self.chk_inactivos = QCheckBox("Ver eliminados")
        self.chk_inactivos.setStyleSheet("color: #E28D8D; font-weight: bold;")
        self.chk_inactivos.stateChanged.connect(lambda _: self.cargar_grilla(self.txt_buscar.text()))
        search_layout.addWidget(self.chk_inactivos)
        
        grid_layout.addLayout(search_layout)

        self.tabla = QTableWidget(0, 5)
        self.tabla.setHorizontalHeaderLabels(["Código", "Descripción", "P. Mostrador", "P. Local", "Stock"])
        self.tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.cellDoubleClicked.connect(self.cargar_producto_para_edicion)
        grid_layout.addWidget(self.tabla)

        splitter.addWidget(grid_widget)
        layout_principal.addWidget(splitter)

    def calcular_precios_desde_costo(self, text=""):
        try:
            costo = float(self.txt_costo_lista.text() or 0)
            flete = float(self.txt_flete.text() or 0)
            utilidad = float(self.txt_utilidad.text() or 0)
            
            costo_final = costo + flete
            precio_contado = costo_final * (1 + (utilidad / 100))
            self.txt_precio_contado.blockSignals(True)
            self.txt_precio_contado.setText(f"{precio_contado:.2f}")
            self.txt_precio_contado.blockSignals(False)

            # Ya no obligamos al precio tarjeta (Local) a ser un +51%, 
            # solo lo pre-llenamos con algo razonable si está en 0 para ayudar.
            if not self.txt_precio_tarjeta.text() or float(self.txt_precio_tarjeta.text() or 0) == 0:
                self.txt_precio_tarjeta.setText(f"{precio_contado:.2f}")

        except ValueError:
            pass

    def calcular_utilidad_desde_precio(self, text=""):
        try:
            costo = float(self.txt_costo_lista.text() or 0)
            flete = float(self.txt_flete.text() or 0)
            precio_contado = float(self.txt_precio_contado.text() or 0)
            
            costo_final = costo + flete
            if costo_final > 0:
                utilidad = ((precio_contado / costo_final) - 1) * 100
            else:
                utilidad = 100.0

            self.txt_utilidad.blockSignals(True)
            self.txt_utilidad.setText(f"{utilidad:.2f}")
            self.txt_utilidad.blockSignals(False)

            if not self.txt_precio_tarjeta.text() or float(self.txt_precio_tarjeta.text() or 0) == 0:
                self.txt_precio_tarjeta.setText(f"{precio_contado:.2f}")

        except ValueError:
            pass

    def cargar_grilla(self, filtro=""):
        self.tabla.setRowCount(0)
        incluir_inactivos = hasattr(self, 'chk_inactivos') and self.chk_inactivos.isChecked()
        productos = ProductosManager.get_all(incluir_inactivos=incluir_inactivos)
        
        cat_filtro = self.cb_filtro_categoria.currentData() if hasattr(self, 'cb_filtro_categoria') else None
        prov_filtro = self.cb_filtro_proveedor.currentData() if hasattr(self, 'cb_filtro_proveedor') else None

        for p in productos:
            if cat_filtro and p['categoria_id'] != cat_filtro:
                continue
                
            if prov_filtro and p['proveedor_id'] != prov_filtro:
                continue
                
            if filtro:
                filtro_lower = filtro.lower()
                coincide = False
                if filtro_lower in p['nombre'].lower():
                    coincide = True
                elif p['codigo_barras'] and filtro_lower in p['codigo_barras'].lower():
                    coincide = True
                elif filtro_lower == str(p['id']):
                    coincide = True
                
                if not coincide:
                    continue
            
            row_idx = self.tabla.rowCount()
            self.tabla.insertRow(row_idx)
            # Mostrar ID interno si no tiene código de barras
            codigo_mostrar = p['codigo_barras'] if p['codigo_barras'] else f"[{p['id']}]"
            item_codigo = QTableWidgetItem(codigo_mostrar)
            item_codigo.setData(Qt.ItemDataRole.UserRole, p['id']) # ID Oculto
            self.tabla.setItem(row_idx, 0, item_codigo)
            
            item_nombre = QTableWidgetItem(p['nombre'])
            if p.get('activo', 1) == 0:
                item_nombre.setForeground(Qt.GlobalColor.red)
                item_nombre.setText(f"{p['nombre']} (ELIMINADO)")
                
            self.tabla.setItem(row_idx, 1, item_nombre)
            self.tabla.setItem(row_idx, 2, QTableWidgetItem(f"{p['precio_contado']:.2f}"))
            self.tabla.setItem(row_idx, 3, QTableWidgetItem(f"{p['precio_tarjeta']:.2f}"))
            self.tabla.setItem(row_idx, 4, QTableWidgetItem(str(p['stock_actual'])))

    def filtrar_grilla(self, texto):
        self.cargar_grilla(texto)

    def cargar_producto_para_edicion(self, row, col):
        item_codigo = self.tabla.item(row, 0)
        if not item_codigo: return
        producto_id = item_codigo.data(Qt.ItemDataRole.UserRole)
        producto = ProductosManager.get_by_id(producto_id)
        if not producto:
            return
            
        self.producto_seleccionado_id = producto['id']
        self.txt_codigo_interno.setText(str(producto['id']))
        self.txt_codigo_barras.setText(producto['codigo_barras'] or "")
        self.txt_codigo_fabrica.setText(producto['codigo_fabrica'] or "")
        self.txt_descripcion.setText(producto['nombre'])
        
        idx_cat = self.cb_categoria.findData(producto['categoria_id'])
        if idx_cat >= 0:
            self.cb_categoria.setCurrentIndex(idx_cat)
            
        idx_prov = self.cb_proveedor.findData(producto['proveedor_id'])
        if idx_prov >= 0:
            self.cb_proveedor.setCurrentIndex(idx_prov)
                
        self.txt_costo_lista.setText(f"{producto['costo_lista']:.2f}")
        self.txt_flete.setText(f"{producto['flete']:.2f}")
        self.txt_utilidad.setText(f"{producto['utilidad_porcentaje']:.2f}")
        self.txt_precio_contado.setText(f"{producto['precio_contado']:.2f}")
        self.txt_precio_tarjeta.setText(f"{producto['precio_tarjeta']:.2f}")
        
        self.txt_stock_actual.setText(str(producto['stock_actual']))
        self.txt_stock_min.setText(str(producto['stock_minimo']))
        self.txt_stock_max.setText(str(producto['stock_maximo']))
        self.txt_ubicacion.setText(producto['ubicacion'] or "")
        
        self.btn_ficha.setEnabled(True)
        if producto.get('activo', 1) == 0:
            self.btn_eliminar.setVisible(False)
            self.btn_restaurar.setVisible(True)
            self.btn_grabar.setEnabled(False)
        else:
            self.btn_eliminar.setEnabled(True)
            self.btn_eliminar.setVisible(True)
            self.btn_restaurar.setVisible(False)
            self.btn_grabar.setEnabled(True)
            self.btn_grabar.setText("Actualizar")

    def limpiar_formulario(self):
        self.txt_codigo_interno.setText("[ Automático ]")
        self.txt_codigo_barras.clear()
        self.txt_codigo_fabrica.clear()
        self.txt_descripcion.clear()
        self.txt_costo_lista.setText("0.00")
        self.txt_flete.setText("0.00")
        self.txt_utilidad.setText("0.00")
        self.txt_precio_contado.setText("0.00")
        self.txt_precio_tarjeta.setText("0.00")
        self.txt_stock_actual.setText("0")
        self.txt_stock_min.setText("5")
        self.txt_stock_max.setText("100")
        self.txt_ubicacion.clear()
        self.producto_seleccionado_id = None
        self.btn_eliminar.setEnabled(False)
        self.btn_eliminar.setVisible(True)
        self.btn_restaurar.setVisible(False)
        self.btn_ficha.setEnabled(False)
        self.btn_grabar.setEnabled(True)
        self.btn_grabar.setText("Guardar (F5)")
        self.txt_codigo_barras.setFocus()

    def eliminar_producto(self):
        if not self.producto_seleccionado_id:
            return
            
        reply = QMessageBox.question(self, "Confirmar", f"¿Está seguro de eliminar el artículo {self.txt_descripcion.text()}?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                ProductosManager.eliminar_producto(self.producto_seleccionado_id)
                QMessageBox.information(self, "Eliminado", "Artículo eliminado correctamente.")
                self.limpiar_formulario()
                self.cargar_grilla(self.txt_buscar.text())
            except Exception as e:
                QMessageBox.critical(self, "Error", f"No se pudo eliminar:\n{str(e)}")

    def restaurar_producto(self):
        if not self.producto_seleccionado_id:
            return
            
        reply = QMessageBox.question(self, "Confirmar", f"¿Desea restaurar el artículo {self.txt_descripcion.text()}?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                ProductosManager.restaurar_producto(self.producto_seleccionado_id)
                QMessageBox.information(self, "Restaurado", "Artículo restaurado correctamente y vuelve a estar activo.")
                self.limpiar_formulario()
                self.cargar_grilla(self.txt_buscar.text())
            except Exception as e:
                QMessageBox.critical(self, "Error", f"No se pudo restaurar:\n{str(e)}")

    def duplicar_producto(self):
        row = self.tabla.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Advertencia", "Seleccione un producto de la grilla para duplicar.")
            return

        codigo_mostrar = self.tabla.item(row, 0).text()
        codigo = codigo_mostrar.replace('[', '').replace(']', '')
        prod = ProductosManager.get_by_codigo(codigo)
        
        if prod:
            self.producto_seleccionado_id = None
            self.txt_codigo_interno.setText("[ Automático ]")
            self.txt_codigo_barras.clear()
            self.txt_codigo_fabrica.clear()
            
            self.txt_descripcion.setText("Copia de " + prod['nombre'])
            self.txt_costo_lista.setText(str(prod['costo_lista']))
            self.txt_flete.setText(str(prod['flete']))
            self.txt_utilidad.setText(str(prod['utilidad_porcentaje']))
            self.txt_precio_contado.setText(str(prod['precio_contado']))
            self.txt_precio_tarjeta.setText(str(prod['precio_tarjeta']))
            
            self.txt_stock_actual.setText(str(prod['stock_actual']))
            self.txt_stock_min.setText(str(prod['stock_minimo']))
            
            self.btn_grabar.setText("Guardar (F5)")
            self.btn_eliminar.setEnabled(False)
            self.btn_ficha.setEnabled(False)
            self.txt_codigo_barras.setFocus()
            QMessageBox.information(self, "Duplicar", "Producto copiado al formulario. Escanee el nuevo código de barras y presione Guardar.")

    def grabar_producto(self):
        try:
            if not self.txt_descripcion.text().strip():
                QMessageBox.warning(self, "Error", "La descripción es obligatoria.")
                return

            cat_data = self.cb_categoria.currentData()
            prov_data = self.cb_proveedor.currentData()
            categoria_id = int(cat_data) if cat_data else None
            proveedor_id = int(prov_data) if prov_data else None

            if self.producto_seleccionado_id:
                # Actualizar
                ProductosManager.actualizar_producto(
                    producto_id=self.producto_seleccionado_id,
                    codigo_barras=self.txt_codigo_barras.text(),
                    codigo_fabrica=self.txt_codigo_fabrica.text(),
                    nombre=self.txt_descripcion.text(),
                    costo_lista=float(self.txt_costo_lista.text()),
                    flete=float(self.txt_flete.text()),
                    utilidad_porcentaje=float(self.txt_utilidad.text()),
                    precio_contado=float(self.txt_precio_contado.text()),
                    precio_tarjeta=float(self.txt_precio_tarjeta.text()),
                    stock_actual=float(self.txt_stock_actual.text()),
                    stock_minimo=float(self.txt_stock_min.text()),
                    stock_maximo=float(self.txt_stock_max.text()),
                    ubicacion=self.txt_ubicacion.text(),
                    categoria_id=categoria_id,
                    proveedor_id=proveedor_id
                )
                QMessageBox.information(self, "Éxito", "Artículo actualizado correctamente.")
            else:
                # Crear Nuevo
                ProductosManager.crear_producto(
                    codigo_barras=self.txt_codigo_barras.text(),
                    codigo_fabrica=self.txt_codigo_fabrica.text(),
                    nombre=self.txt_descripcion.text(),
                    costo_lista=float(self.txt_costo_lista.text()),
                    flete=float(self.txt_flete.text()),
                    utilidad_porcentaje=float(self.txt_utilidad.text()),
                    precio_contado=float(self.txt_precio_contado.text()),
                    precio_tarjeta=float(self.txt_precio_tarjeta.text()),
                    stock_actual=float(self.txt_stock_actual.text()),
                    stock_minimo=float(self.txt_stock_min.text()),
                    stock_maximo=float(self.txt_stock_max.text()),
                    ubicacion=self.txt_ubicacion.text(),
                    categoria_id=categoria_id,
                    proveedor_id=proveedor_id
                )
                QMessageBox.information(self, "Éxito", "Artículo guardado correctamente.")
                
            self.limpiar_formulario()
            self.cargar_grilla()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo guardar:\n{str(e)}")

    def showEvent(self, event):
        super().showEvent(event)
        self.cargar_combos()

    def ver_ficha_producto(self):
        if not self.producto_seleccionado_id:
            return
            
        historial = ProductosManager.get_historial_producto(self.producto_seleccionado_id)
        
        from PyQt6.QtWidgets import QDialog
        
        class FichaDialog(QDialog):
            def __init__(self, parent=None, producto_nombre="", historial_data=None):
                super().__init__(parent)
                self.setWindowTitle(f"Ficha / Historial: {producto_nombre}")
                self.setMinimumSize(700, 400)
                self.setStyleSheet("""
                    QDialog { background-color: #1A2026; }
                    QLabel { color: #cdd6f4; font-size: 14px; }
                    QTableWidget {
                        background-color: #242A32;
                        color: #cdd6f4;
                        gridline-color: #32404D;
                        border: 1px solid #32404D;
                        border-radius: 6px;
                    }
                    QHeaderView::section {
                        background-color: #1A2026;
                        color: #a6adc8;
                        padding: 8px;
                        border: none;
                        font-weight: bold;
                        border-bottom: 2px solid #32404D;
                    }
                    QPushButton {
                        background-color: #32404D;
                        color: #cdd6f4;
                        border: none;
                        border-radius: 6px;
                        padding: 8px 20px;
                        font-weight: bold;
                    }
                    QPushButton:hover { background-color: #8DE2B9; color: #1A2026; }
                """)
                
                layout = QVBoxLayout(self)
                
                lbl_titulo = QLabel(f"Movimientos de: {producto_nombre}")
                lbl_titulo.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
                lbl_titulo.setStyleSheet("color: #ACE0F4;")
                layout.addWidget(lbl_titulo)
                
                tabla = QTableWidget(0, 6)
                tabla.setHorizontalHeaderLabels(["Fecha", "Cliente", "Método Pago", "Cant.", "Precio Unit.", "Subtotal"])
                tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
                tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
                tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
                
                for mov in historial_data:
                    row = tabla.rowCount()
                    tabla.insertRow(row)
                    tabla.setItem(row, 0, QTableWidgetItem(mov['fecha']))
                    tabla.setItem(row, 1, QTableWidgetItem(mov['cliente']))
                    tabla.setItem(row, 2, QTableWidgetItem(mov['metodo_pago']))
                    tabla.setItem(row, 3, QTableWidgetItem(str(mov['cantidad'])))
                    tabla.setItem(row, 4, QTableWidgetItem(f"${mov['precio_unitario']:.2f}"))
                    tabla.setItem(row, 5, QTableWidgetItem(f"${mov['subtotal']:.2f}"))
                
                layout.addWidget(tabla)
                
                btn_cerrar = QPushButton("Cerrar")
                btn_cerrar.clicked.connect(self.accept)
                btn_layout = QHBoxLayout()
                btn_layout.addStretch()
                btn_layout.addWidget(btn_cerrar)
                layout.addLayout(btn_layout)
                
        dialog = FichaDialog(self, self.txt_descripcion.text(), historial)
        dialog.exec()
