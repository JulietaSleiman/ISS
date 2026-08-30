import openpyxl
import os

file_path = "LISTA DE PRECIOS BEBIDAS FRIAS 10-07 (version 1)(Recuperado automáticamente).xlsx"

if not os.path.exists(file_path):
    print("El archivo no existe")
else:
    wb = openpyxl.load_workbook(file_path, data_only=True)
    ws = wb.active
    print("Hoja activa:", ws.title)
    print("Primeras 20 filas:")
    for i, row in enumerate(ws.iter_rows(min_row=1, max_row=20, values_only=True)):
        print(f"Fila {i+1}: {row}")
