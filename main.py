import sys
from PyQt6.QtWidgets import QApplication, QDialog
from src.db.database import init_db
from src.ui.main_window import MainWindow
from src.ui.login_dialog import LoginDialog
from src.core.auth_manager import AuthManager

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
        background-color: #F8FAFC;
        color: #0F172A;
        font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, Arial, sans-serif;
    }
    
    /* Entradas de texto, selectores y campos numéricos */
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit, QDateTimeEdit {
        background-color: #FFFFFF;
        color: #0F172A;
        border: 1px solid #CBD5E1;
        border-radius: 6px;
        padding: 8px 12px;
        font-size: 14px;
    }
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus {
        border: 1.5px solid #0284C7;
        background-color: #FFFFFF;
    }
    QLineEdit:disabled, QComboBox:disabled {
        background-color: #F1F5F9;
        color: #94A3B8;
        border-color: #E2E8F0;
    }
    QComboBox::drop-down {
        border: none;
        padding-right: 8px;
    }
    QComboBox QAbstractItemView {
        background-color: #FFFFFF;
        color: #0F172A;
        selection-background-color: #E0F2FE;
        selection-color: #0284C7;
        border: 1px solid #CBD5E1;
    }
    
    /* Tablas */
    QTableWidget {
        background-color: #FFFFFF;
        alternate-background-color: #F8FAFC;
        color: #0F172A;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        gridline-color: #F1F5F9;
        font-size: 14px;
        selection-background-color: #E0F2FE;
        selection-color: #0284C7;
        outline: none;
    }
    QTableWidget::item {
        padding: 6px;
        border-bottom: 1px solid #F1F5F9;
    }
    QHeaderView::section {
        background-color: #F1F5F9;
        color: #475569;
        padding: 10px 8px;
        border: none;
        border-bottom: 2px solid #CBD5E1;
        font-weight: 600;
        text-transform: uppercase;
        font-size: 12px;
    }
    
    /* Botones Genéricos */
    QPushButton {
        background-color: #FFFFFF;
        color: #0F172A;
        border: 1px solid #CBD5E1;
        border-radius: 6px;
        padding: 9px 16px;
        font-weight: 600;
        font-size: 14px;
    }
    QPushButton:hover {
        background-color: #F1F5F9;
        border-color: #94A3B8;
    }
    QPushButton:pressed {
        background-color: #E2E8F0;
    }
    QPushButton:disabled {
        background-color: #F8FAFC;
        color: #94A3B8;
        border-color: #E2E8F0;
    }
    
    /* Dialogos y Ventanas Emergentes */
    QDialog {
        background-color: #F8FAFC;
        color: #0F172A;
    }
    
    /* Pestañas / Tabs */
    QTabWidget::pane {
        border: 1px solid #E2E8F0;
        background-color: #FFFFFF;
        border-radius: 8px;
    }
    QTabBar::tab {
        background-color: #E2E8F0;
        color: #475569;
        padding: 9px 18px;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
        font-weight: 600;
        font-size: 13px;
        margin-right: 3px;
    }
    QTabBar::tab:selected {
        background-color: #FFFFFF;
        color: #0284C7;
        border-bottom: 2px solid #0284C7;
    }
    
    /* Scrollbars */
    QScrollBar:vertical {
        border: none;
        background: #F1F5F9;
        width: 10px;
        margin: 0px;
    }
    QScrollBar::handle:vertical {
        background: #CBD5E1;
        min-height: 20px;
        border-radius: 5px;
    }
    QScrollBar::handle:vertical:hover {
        background: #94A3B8;
    }
    QScrollBar:horizontal {
        border: none;
        background: #F1F5F9;
        height: 10px;
        margin: 0px;
    }
    QScrollBar::handle:horizontal {
        background: #CBD5E1;
        min-width: 20px;
        border-radius: 5px;
    }
    QScrollBar::handle:horizontal:hover {
        background: #94A3B8;
    }
    """
    app.setStyleSheet(modern_style)
    
    # No se crea ninguna vista operativa antes de autenticar al responsable.
    exit_code = 0
    while True:
        dialog = LoginDialog()
        if dialog.exec() != QDialog.DialogCode.Accepted:
            break
        window = MainWindow()
        window.showMaximized()
        exit_code = app.exec()
        AuthManager.logout()
        if not window.login_again:
            break
        window.deleteLater()
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
