@echo off
echo =========================================
echo COMPILANDO SISTEMA DE VENTAS - IVAN LLORENS
echo =========================================

echo Instalando PyInstaller...
pip install pyinstaller

echo.
echo Limpiando compilaciones anteriores...
rmdir /s /q build
rmdir /s /q dist

echo.
echo Generando ejecutable (Onefile)...
python -m PyInstaller --noconfirm --onefile --windowed --icon="logo.ico" --name "SistemaIvanLlorens" --add-data "logo.jpg;." --add-data "logo.png;." main.py

echo.
echo =========================================
echo COMPILACION TERMINADA
echo El ejecutable esta en la carpeta "dist\SistemaIvanLlorens.exe"
echo =========================================
pause
