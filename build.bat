@echo off
echo =========================================
echo COMPILANDO SISTEMA DRUGSTORE
echo =========================================

echo Instalando PyInstaller...
pip install pyinstaller

echo.
echo Limpiando compilaciones anteriores...
rmdir /s /q build
rmdir /s /q dist

echo.
echo Generando ejecutable...
python -m PyInstaller --noconfirm --onedir --windowed --icon="logo.ico" --name "SistemaBebidas" --add-data "logo.jpg;." main.py

echo.
echo =========================================
echo COMPILACION TERMINADA
echo El ejecutable esta en la carpeta "dist\SistemaBebidas"
echo =========================================
pause
