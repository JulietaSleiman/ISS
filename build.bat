@echo off
setlocal
pushd "%~dp0"
if errorlevel 1 exit /b 1

echo PREPARANDO SISTEMA DE VENTAS - IVAN LLORENS
python --version >nul 2>&1
if errorlevel 1 goto python_missing
python -c "import PyInstaller, PyQt6, packaging" >nul 2>&1
if errorlevel 1 goto dependencies_missing
python scripts\check_release_version.py
if errorlevel 1 goto failed

echo Generando ejecutable Onefile...
python -m PyInstaller --clean --noconfirm --onefile --windowed --icon="logo.ico" --name="SistemaIvanLlorens" --add-data="logo.jpg;." --add-data="logo.png;." --add-data="logo.ico;." main.py
if errorlevel 1 goto failed
echo Compilacion terminada: dist\SistemaIvanLlorens.exe
popd
exit /b 0

:python_missing
echo ERROR: Python no esta disponible en PATH.
goto failed

:dependencies_missing
echo ERROR: Faltan dependencias. Active su entorno e instale manualmente:
echo python -m pip install -r requirements.txt
goto failed

:failed
echo No se genero una distribucion nueva. Revise el error anterior.
popd
exit /b 1
