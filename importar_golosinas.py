import openpyxl
import os
import sys
import re

# Ensure we can import from src
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.db.database import get_connection

def importar_golosinas():
    file_path = "LISTA DE PRECIOS GOLOSINAS.xlsx"
    
    if not os.path.exists(file_path):
        print("Error: No se encontró el archivo Excel de golosinas.")
        return

    print("Abriendo archivo Excel...")
    wb = openpyxl.load_workbook(file_path, data_only=True)
    ws = wb.active
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Crear categoría 'Golosinas' si no existe
    cursor.execute("SELECT id FROM categorias WHERE nombre = 'Golosinas'")
    categoria = cursor.fetchone()
    if not categoria:
        cursor.execute("INSERT INTO categorias (nombre) VALUES ('Golosinas')")
        categoria_id = cursor.lastrowid
    else:
        categoria_id = categoria['id']

    productos_agregados = 0
    productos_actualizados = 0
    
    print("Iniciando importación...")
    # Iterar sobre las filas a partir de la fila 11 (los datos empiezan en la 11 según vimos)
    for row in ws.iter_rows(min_row=11, values_only=True):
        nombre_original = row[0]
        costo_unidad_mas_iva = row[9] # Costo X UNIDAD MAS21
        precio_final_str = row[14]    # PRECIO FINAL
        
        if nombre_original is None or str(nombre_original).strip() == "":
            continue
            
        nombre = str(nombre_original).strip()
        # Eliminar cosas como 'x12', 'x24', 'X6' si se desea, o dejarlas.
        # Las golosinas a veces se venden por unidad. Vamos a limpiar un poco.
        nombre = re.sub(r'(?i)\bx\d+\b', '', nombre)
        nombre = " ".join(nombre.split())
        
        # Parsear costo final - Forzado a 0 según instrucción
        costo_final = 0.0

        # Parsear precio contado (Columna Ñ - index 14)
        precio_contado = 0.0
        if precio_final_str is not None:
            try:
                precio_contado = float(precio_final_str)
            except ValueError:
                pass
                
        precio_tarjeta = precio_contado * 1.51
        
        # Verificar si el producto ya existe por nombre
        cursor.execute("SELECT id FROM productos WHERE nombre = ?", (nombre,))
        producto_existente = cursor.fetchone()
        
        if producto_existente:
            # Actualizar precios
            cursor.execute("""
                UPDATE productos 
                SET costo_final = ?, precio_contado = ?, precio_tarjeta = ?, categoria_id = ?
                WHERE id = ?
            """, (costo_final, precio_contado, precio_tarjeta, categoria_id, producto_existente['id']))
            productos_actualizados += 1
        else:
            # Insertar nuevo
            cursor.execute("""
                INSERT INTO productos (
                    codigo_barras, codigo_fabrica, nombre, costo_lista, flete,
                    costo_final, utilidad_porcentaje, precio_contado, precio_tarjeta,
                    stock_actual, stock_minimo, stock_maximo, ubicacion,
                    categoria_id, proveedor_id
                ) VALUES (
                    NULL, '', ?, 0.0, 0.0, 
                    ?, 0.0, ?, ?, 
                    0, 5, 100, '',
                    ?, NULL
                )
            """, (nombre, costo_final, precio_contado, precio_tarjeta, categoria_id))
            productos_agregados += 1
        
    conn.commit()
    conn.close()
    
    print(f"¡Importación exitosa!")
    print(f"Nuevos productos agregados: {productos_agregados}")
    print(f"Productos existentes actualizados: {productos_actualizados}")

if __name__ == "__main__":
    importar_golosinas()
