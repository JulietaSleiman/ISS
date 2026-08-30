import sqlite3
import re

def fix_names():
    conn = sqlite3.connect('database.sqlite')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Seleccionamos solo las golosinas
    cursor.execute("SELECT id, nombre FROM productos WHERE categoria_id = (SELECT id FROM categorias WHERE nombre = 'Golosinas')")
    productos = cursor.fetchall()
    
    actualizados = 0
    for p in productos:
        nombre_original = p['nombre']
        
        # Regla 1: Reemplazar "24x20gs" -> "20gs" (quitar el multiplicador de cantidad de la caja)
        # Esto quita cualquier número seguido de una 'x' que esté justo antes de un número con letras.
        nombre_nuevo = re.sub(r'\b\d+x(?=\d+[a-zA-Z]+)', '', nombre_original, flags=re.IGNORECASE)
        
        # Regla 2: Eliminar cosas como "x20u" o "x 20 u" 
        nombre_nuevo = re.sub(r'\bx\s*\d+\s*u\b', '', nombre_nuevo, flags=re.IGNORECASE)
        
        # Limpiar dobles espacios que puedan quedar
        nombre_nuevo = " ".join(nombre_nuevo.split())
        
        if nombre_original != nombre_nuevo:
            print(f"Modificando: '{nombre_original}'  ->  '{nombre_nuevo}'")
            cursor.execute("UPDATE productos SET nombre = ? WHERE id = ?", (nombre_nuevo, p['id']))
            actualizados += 1
            
    conn.commit()
    conn.close()
    
    print(f"Se corrigieron {actualizados} nombres de productos.")

if __name__ == "__main__":
    fix_names()
