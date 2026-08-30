import sys
from PyQt6.QtWidgets import QApplication
from src.db.database import init_db
from src.ui.main_window import MainWindow

def main():
    # 1. Inicializar la base de datos (crea el archivo y tablas si no existen)
    print("Inicializando base de datos...")
    init_db()
    
    # 2. Iniciar la aplicación PyQt
    app = QApplication(sys.argv)
    
    # Configurar estilo global moderno
    app.setStyle("Fusion")
    
    modern_style = """
    /* Fondo principal y textos */
    QWidget {
        background-color: #1A2026;
        color: #E5EEF2;
        font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, Arial, sans-serif;
    }
    
    /* Entradas de texto */
    QLineEdit, QComboBox {
        background-color: #232B33;
        color: #E5EEF2;
        border: 1px solid #32404D;
        border-radius: 6px;
        padding: 8px 12px;
        font-size: 14px;
    }
    QLineEdit:focus, QComboBox:focus {
        border: 1px solid #ACE0F4;
        background-color: #28323B;
    }
    
    /* Tablas */
    QTableWidget {
        background-color: #1A2026;
        alternate-background-color: #1F262E;
        border: 1px solid #32404D;
        border-radius: 8px;
        gridline-color: transparent;
        font-size: 14px;
        selection-background-color: #2C3742;
        selection-color: #ACE0F4;
        outline: none;
    }
    QTableWidget::item {
        padding: 4px;
        border-bottom: 1px solid #232B33;
    }
    QHeaderView::section {
        background-color: #232B33;
        color: #9EB3C2;
        padding: 12px 8px;
        border: none;
        border-bottom: 2px solid #32404D;
        font-weight: 600;
        text-transform: uppercase;
        font-size: 12px;
    }
    
    /* Botones Genéricos */
    QPushButton {
        background-color: #232B33;
        color: #E5EEF2;
        border: 1px solid #32404D;
        border-radius: 6px;
        padding: 10px 16px;
        font-weight: 600;
        font-size: 14px;
    }
    QPushButton:hover {
        background-color: #2C3742;
        border-color: #91C2D5;
        color: #ACE0F4;
    }
    QPushButton:pressed {
        background-color: #32404D;
        color: #E5EEF2;
    }
    
    /* Scrollbars */
    QScrollBar:vertical {
        border: none;
        background: #1A2026;
        width: 10px;
        margin: 0px;
    }
    QScrollBar::handle:vertical {
        background: #32404D;
        min-height: 20px;
        border-radius: 5px;
    }
    QScrollBar::handle:vertical:hover {
        background: #425961;
    }
    """
    app.setStyleSheet(modern_style)
    
    # 3. Crear y mostrar ventana principal
    window = MainWindow()
    window.showMaximized() # Mejor maximizado por defecto
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
