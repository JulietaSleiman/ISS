import sys
import re
from pathlib import Path
from openpyxl import load_workbook
import sqlite3

def limpiar_nombre(nombre):
    nombre = nombre.upper().strip()
    # Sacar 'x12', 'x 12', 'x 20 u', etc. en cualquier parte del string
    nombre = re.sub(r'\s*[xX]\s*\d+\b(?:\s*[uU]\b)?', ' ', nombre)
    # Reemplazar comas por puntos en gramajes "1,5 L" -> "1.5 L"
    nombre = re.sub(r'(\d+),(\d+)', r'\1.\2', nombre)
    # Reemplazar acentos comunes si hiciera falta, pero SQLite es case insensitive en ASCII.
    # Quitamos dobles espacios
    nombre = re.sub(r'\s+', ' ', nombre)
    return nombre.strip()

file_name = "LISTA DE PRECIOS BEBIDAS FRIAS 10-07 (version 1)(Recuperado automáticamente).xlsx"
wb = load_workbook(file_name, data_only=True)
ws = wb.active

header_row = next(ws.iter_rows(min_row=1, max_row=1, values_only=True))
col_consumir_idx = 9 # Default J

for i, h in enumerate(header_row):
    if h and "CONSUMIR AC" in str(h).upper():
        col_consumir_idx = i
        break

DB_PATH = Path("database.sqlite")
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

actualizados = 0

for row in ws.iter_rows(min_row=2, values_only=True):
    nombre_excel = str(row[0]).strip() if row[0] is not None else ""
    precio_local_val = row[col_consumir_idx]
    
    if not nombre_excel or nombre_excel.lower() == 'nan' or precio_local_val is None:
        continue
        
    try:
        precio_local = float(precio_local_val)
        if precio_local > 0:
            nombre_limpio = limpiar_nombre(nombre_excel)
            
            # Buscamos primero nombre exacto sin case
            cursor.execute("UPDATE productos SET precio_tarjeta = ? WHERE UPPER(nombre) = ?", (precio_local, nombre_limpio))
            if cursor.rowcount > 0:
                actualizados += cursor.rowcount
            else:
                # Si no, buscar por LIKE en cada parte clave
                partes = nombre_limpio.split()
                if len(partes) >= 1:
                    like_str = "%" + "%".join(partes) + "%"
                    cursor.execute("UPDATE productos SET precio_tarjeta = ? WHERE UPPER(nombre) LIKE ?", (precio_local, like_str))
                    actualizados += cursor.rowcount
                    
    except (ValueError, TypeError):
        pass

conn.commit()

import shutil
destino_produccion = Path("C:/BebidasFrias/database.sqlite")
if destino_produccion.exists():
    try:
        shutil.copy2(DB_PATH, destino_produccion)
        print("También se copió la base de datos a C:\\BebidasFrias\\database.sqlite automáticamente.")
    except Exception as e:
        pass

conn.close()
print(f"Completado. Se actualizaron los precios locales de {actualizados} productos.")
