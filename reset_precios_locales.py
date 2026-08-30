import sqlite3
from pathlib import Path

def reset_precio_local(db_path):
    if db_path.exists():
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("UPDATE productos SET precio_tarjeta = 0.0")
            count = cursor.rowcount
            conn.commit()
            conn.close()
            print(f"Borrados los precios locales de {count} productos en {db_path}")
        except Exception as e:
            print(f"Error actualizando {db_path}: {e}")
    else:
        print(f"No se encontró base de datos en {db_path}")

if __name__ == "__main__":
    # Base de datos de desarrollo
    reset_precio_local(Path("database.sqlite"))
    
    # Base de datos de producción
    reset_precio_local(Path("C:/BebidasFrias/database.sqlite"))
