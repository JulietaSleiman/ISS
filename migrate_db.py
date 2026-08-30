import sqlite3
import os
from pathlib import Path

DB_PATH = Path("c:/Users/CS/OneDrive/Escritorio/¿/Bebidas frias/database.sqlite")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

try:
    cursor.execute("PRAGMA foreign_keys=off;")
    cursor.execute("BEGIN TRANSACTION;")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ventas_detalle_new (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        venta_id INTEGER NOT NULL,
        producto_id INTEGER,
        promocion_id INTEGER,
        cantidad REAL NOT NULL,
        precio_unitario REAL NOT NULL,
        subtotal REAL NOT NULL,
        FOREIGN KEY (venta_id) REFERENCES ventas (id),
        FOREIGN KEY (producto_id) REFERENCES productos (id),
        FOREIGN KEY (promocion_id) REFERENCES promociones (id)
    );
    """)
    cursor.execute("INSERT INTO ventas_detalle_new (id, venta_id, producto_id, cantidad, precio_unitario, subtotal) SELECT id, venta_id, producto_id, cantidad, precio_unitario, subtotal FROM ventas_detalle;")
    cursor.execute("DROP TABLE ventas_detalle;")
    cursor.execute("ALTER TABLE ventas_detalle_new RENAME TO ventas_detalle;")
    cursor.execute("COMMIT;")
    cursor.execute("PRAGMA foreign_keys=on;")
    print("Migración de base de datos exitosa.")
except Exception as e:
    conn.rollback()
    print("Error:", e)
finally:
    conn.close()
