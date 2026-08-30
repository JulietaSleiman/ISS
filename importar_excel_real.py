import openpyxl
import os
import sys

# Ensure we can import from src
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.db.database import get_connection

def importar_datos():
    file_path = "LISTA DE PRECIOS BEBIDAS FRIAS 10-07 (version 1)(Recuperado automáticamente).xlsx"
    
    if not os.path.exists(file_path):
        print("Error: No se encontró el archivo Excel.")
        return

    print("Abriendo archivo Excel...")
    wb = openpyxl.load_workbook(file_path, data_only=True)
    ws = wb.active
    
    conn = get_connection()
    cursor = conn.cursor()
    
    productos_agregados = 0
    
    import re

    print("Iniciando importación...")
    # Iterar sobre las filas, saltando la cabecera (fila 1)
    for row in ws.iter_rows(min_row=2, values_only=True):
        nombre_bebida = row[0]
        precio_str = row[7]
        
        if nombre_bebida is None or str(nombre_bebida).strip() == "":
            continue
            
        nombre = str(nombre_bebida).strip()
        # Eliminar 'x12', 'x24', 'X6', etc. y limpiar dobles espacios
        nombre = re.sub(r'(?i)\bx\d+\b', '', nombre)
        nombre = " ".join(nombre.split())
        
        # Parsear precio contado
        precio_contado = 0.0
        if precio_str is not None:
            try:
                precio_contado = float(precio_str)
            except ValueError:
                precio_contado = 0.0
                
        precio_tarjeta = precio_contado * 1.51
        
        cursor.execute("""
            INSERT INTO productos (
                codigo_barras, codigo_fabrica, nombre, costo_lista, flete,
                utilidad_porcentaje, precio_contado, precio_tarjeta,
                stock_actual, stock_minimo, stock_maximo, ubicacion,
                categoria_id, proveedor_id
            ) VALUES (
                NULL, '', ?, 0.0, 0.0, 
                0.0, ?, ?, 
                0, 5, 100, '',
                NULL, NULL
            )
        """, (nombre, precio_contado, precio_tarjeta))
        productos_agregados += 1
        
    conn.commit()
    conn.close()
    
    print(f"¡Importación exitosa! Se agregaron {productos_agregados} productos a la base de datos.")

if __name__ == "__main__":
    importar_datos()
