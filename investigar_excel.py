import sys
import re
from pathlib import Path
from openpyxl import load_workbook
import sqlite3

# Función de limpieza (igual que la que usamos para limpiar la BD)
def limpiar_nombre(nombre):
    nombre = nombre.upper().strip()
    
    # 1. Eliminar todo el texto desde " x" seguido de números y una "U" (ej: " x20u")
    # Buscamos patrones como " x 20u", " X20 U", "X20U" al final o en medio
    nombre = re.sub(r'\s*[xX]\s*\d+\s*[uU]\b.*', '', nombre)
    
    # También limpiar si está sin la U: " x 20", " x20" si están al final
    nombre = re.sub(r'\s*[xX]\s*\d+\s*$', '', nombre)
    
    # 2. Reemplazar comas por puntos en gramajes "1,5 L" -> "1.5 L"
    nombre = re.sub(r'(\d+),(\d+)', r'\1.\2', nombre)
    
    # 3. Eliminar espacios múltiples
    nombre = re.sub(r'\s+', ' ', nombre)
    
    return nombre.strip()

file_name = "LISTA DE PRECIOS BEBIDAS FRIAS 10-07 (version 1)(Recuperado automáticamente).xlsx"
wb = load_workbook(file_name, data_only=True)
ws = wb.active

# Buscar la columna "CONSUMIR ACÁ"
header_row = next(ws.iter_rows(min_row=1, max_row=1, values_only=True))
print("Cabeceras encontradas:")
for i, h in enumerate(header_row):
    print(f"Col {i}: {h}")

col_consumir_idx = -1
for i, h in enumerate(header_row):
    if h and "CONSUMIR AC" in str(h).upper():
        col_consumir_idx = i
        break

if col_consumir_idx == -1:
    print("NO SE ENCONTRÓ LA COLUMNA 'CONSUMIR ACÁ'. Fallback a J (9).")
    col_consumir_idx = 9
else:
    print(f"Se encontró la columna en el índice {col_consumir_idx}")

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
            
            # Buscar en DB por nombre limpio
            cursor.execute("UPDATE productos SET precio_tarjeta = ? WHERE nombre = ?", (precio_local, nombre_limpio))
            if cursor.rowcount > 0:
                actualizados += cursor.rowcount
            else:
                # Fallback con LIKE usando la primera parte del nombre
                partes = nombre_limpio.split()
                if len(partes) >= 2:
                    nombre_like = f"%{partes[0]} {partes[1]}%"
                    cursor.execute("UPDATE productos SET precio_tarjeta = ? WHERE nombre LIKE ?", (precio_local, nombre_like))
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
        print(f"No se pudo copiar a producción: {e}")

conn.close()
print(f"Completado. Se actualizaron los precios locales de {actualizados} productos.")
