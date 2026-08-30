import sqlite3
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

if getattr(sys, 'frozen', False):
    # En producción (el .exe), la base de datos se guarda en C:\BebidasFrias
    DB_DIR = Path("C:/BebidasFrias")
    try:
        DB_DIR.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        # Fallback por si hay restricciones raras de Windows, aunque en C:\ no suele haber si creamos una carpeta propia
        DB_DIR = Path(os.environ.get('LOCALAPPDATA', os.environ.get('APPDATA', os.path.expanduser('~')))) / "BebidasFrias"
        DB_DIR.mkdir(parents=True, exist_ok=True)
else:
    # Si se ejecuta como script .py (desarrollo), se guarda en la raíz del proyecto
    DB_DIR = Path(__file__).parent.parent.parent

DB_PATH = DB_DIR / "database.sqlite"

def local_time_row_factory(cursor, row):
    raw = sqlite3.Row(cursor, row)
    class Proxy:
        def __getitem__(self, key):
            val = raw[key]
            col = cursor.description[key][0] if isinstance(key, int) else key
            # Solo convertir si es string y el nombre de la columna parece ser una fecha/timestamp
            if isinstance(val, str) and ('fecha' in col or col in ('apertura', 'cierre', 'ultimo_backup')):
                try:
                    # SQLite guarda CURRENT_TIMESTAMP en formato 'YYYY-MM-DD HH:MM:SS' UTC
                    dt_utc = datetime.strptime(val, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
                    # Convertir a zona horaria local
                    return dt_utc.astimezone().strftime('%Y-%m-%d %H:%M:%S')
                except Exception:
                    # Si falla (p.ej no es un datetime válido), retornamos original
                    return val
            return val
        def keys(self):
            return raw.keys()
        def get(self, key, default=None):
            try:
                return self[key]
            except (KeyError, IndexError):
                return default
    return Proxy()

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = local_time_row_factory
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS categorias (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL UNIQUE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS proveedores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        telefono TEXT,
        direccion TEXT,
        activo INTEGER DEFAULT 1
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS productos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        codigo_barras TEXT UNIQUE,
        codigo_fabrica TEXT,
        nombre TEXT NOT NULL,
        costo_lista REAL NOT NULL DEFAULT 0.0,
        flete REAL NOT NULL DEFAULT 0.0,
        costo_final REAL NOT NULL DEFAULT 0.0,
        utilidad_porcentaje REAL NOT NULL DEFAULT 0.0,
        precio_contado REAL NOT NULL DEFAULT 0.0,
        precio_tarjeta REAL NOT NULL DEFAULT 0.0,
        stock_actual REAL NOT NULL DEFAULT 0.0,
        stock_minimo REAL NOT NULL DEFAULT 5.0,
        stock_maximo REAL NOT NULL DEFAULT 100.0,
        unidades_bulto INTEGER DEFAULT 1,
        ubicacion TEXT,
        observaciones TEXT,
        categoria_id INTEGER,
        proveedor_id INTEGER,
        activo INTEGER DEFAULT 1,
        FOREIGN KEY (categoria_id) REFERENCES categorias (id),
        FOREIGN KEY (proveedor_id) REFERENCES proveedores (id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS clientes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        cuit TEXT,
        domicilio TEXT,
        localidad TEXT,
        provincia TEXT,
        condicion_iva TEXT DEFAULT 'Consumidor Final',
        telefono TEXT,
        condicion_pago TEXT DEFAULT 'Contado',
        descuento_porcentaje REAL DEFAULT 0.0,
        activo INTEGER DEFAULT 1
    )
    """)

    cursor.execute("SELECT id FROM clientes WHERE id = 1")
    if not cursor.fetchone():
        cursor.execute("""
        INSERT INTO clientes (id, nombre, cuit, condicion_iva, activo) 
        VALUES (1, 'CONSUMIDOR FINAL', '00000000000', 'Consumidor Final', 1)
        """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS caja_sesiones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha_apertura DATETIME DEFAULT CURRENT_TIMESTAMP,
        fecha_cierre DATETIME,
        monto_inicial REAL NOT NULL DEFAULT 0.0,
        monto_cierre REAL,
        estado TEXT DEFAULT 'ABIERTA'
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS caja_movimientos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        caja_sesion_id INTEGER NOT NULL,
        tipo TEXT NOT NULL,
        monto REAL NOT NULL,
        metodo_pago TEXT NOT NULL,
        descripcion TEXT,
        fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (caja_sesion_id) REFERENCES caja_sesiones (id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ventas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cliente_id INTEGER NOT NULL,
        caja_sesion_id INTEGER NOT NULL,
        fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
        subtotal REAL NOT NULL,
        descuento_total REAL NOT NULL DEFAULT 0.0,
        total REAL NOT NULL,
        metodo_pago TEXT NOT NULL,
        tipo_comprobante TEXT DEFAULT 'TICKET',
        estado_afip TEXT DEFAULT 'PENDIENTE',
        nro_comprobante_afip TEXT,
        estado TEXT DEFAULT 'COMPLETADA',
        FOREIGN KEY (cliente_id) REFERENCES clientes (id),
        FOREIGN KEY (caja_sesion_id) REFERENCES caja_sesiones (id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ventas_detalle (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        venta_id INTEGER NOT NULL,
        producto_id INTEGER,
        promocion_id INTEGER,
        cantidad REAL NOT NULL,
        precio_unitario REAL NOT NULL,
        costo_unitario REAL NOT NULL DEFAULT 0.0,
        subtotal REAL NOT NULL,
        FOREIGN KEY (venta_id) REFERENCES ventas (id),
        FOREIGN KEY (producto_id) REFERENCES productos (id),
        FOREIGN KEY (promocion_id) REFERENCES promociones (id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS promociones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        precio_fijo REAL NOT NULL,
        activa INTEGER DEFAULT 1
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS promocion_detalles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        promocion_id INTEGER NOT NULL,
        producto_id INTEGER NOT NULL,
        cantidad_requerida INTEGER NOT NULL,
        FOREIGN KEY(promocion_id) REFERENCES promociones(id),
        FOREIGN KEY(producto_id) REFERENCES productos(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cta_cte_movimientos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cliente_id INTEGER NOT NULL,
        caja_sesion_id INTEGER,
        venta_id INTEGER,
        fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
        tipo TEXT NOT NULL, -- 'DEUDA' o 'PAGO'
        monto REAL NOT NULL,
        detalle TEXT,
        FOREIGN KEY (cliente_id) REFERENCES clientes (id),
        FOREIGN KEY (caja_sesion_id) REFERENCES caja_sesiones (id),
        FOREIGN KEY (venta_id) REFERENCES ventas (id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cta_cte_proveedores_movimientos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        proveedor_id INTEGER NOT NULL,
        caja_sesion_id INTEGER,
        fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
        tipo TEXT NOT NULL, -- 'DEUDA' o 'PAGO'
        monto REAL NOT NULL,
        detalle TEXT,
        FOREIGN KEY (proveedor_id) REFERENCES proveedores (id),
        FOREIGN KEY (caja_sesion_id) REFERENCES caja_sesiones (id)
    )
    """)

    # -- MIGRACIONES AUTOMÁTICAS --

    cursor.execute("PRAGMA table_info(ventas_detalle)")
    columnas_vd = [col['name'] for col in cursor.fetchall()]
    
    if 'promocion_id' not in columnas_vd or 'costo_unitario' not in columnas_vd:
        try:
            cursor.execute("CREATE TABLE ventas_detalle_new (id INTEGER PRIMARY KEY AUTOINCREMENT, venta_id INTEGER NOT NULL, producto_id INTEGER, promocion_id INTEGER, cantidad REAL NOT NULL, precio_unitario REAL NOT NULL, costo_unitario REAL NOT NULL DEFAULT 0.0, subtotal REAL NOT NULL, FOREIGN KEY (venta_id) REFERENCES ventas (id), FOREIGN KEY (producto_id) REFERENCES productos (id), FOREIGN KEY (promocion_id) REFERENCES promociones (id))")
            
            cols_to_select = ["id", "venta_id", "producto_id", "cantidad", "precio_unitario", "subtotal"]
            if 'promocion_id' in columnas_vd:
                cols_to_select.append("promocion_id")
            if 'costo_unitario' in columnas_vd:
                cols_to_select.append("costo_unitario")
                
            cols_str = ", ".join(cols_to_select)
            
            cursor.execute(f"INSERT INTO ventas_detalle_new ({cols_str}) SELECT {cols_str} FROM ventas_detalle")
            cursor.execute("DROP TABLE ventas_detalle")
            cursor.execute("ALTER TABLE ventas_detalle_new RENAME TO ventas_detalle")
        except Exception as e:
            print("Error en migración automática de estructura:", e)

    # Migrar costo histórico para ventas pasadas
    try:
        # Productos simples
        cursor.execute("""
        UPDATE ventas_detalle 
        SET costo_unitario = (
            SELECT costo_final FROM productos WHERE productos.id = ventas_detalle.producto_id
        )
        WHERE (costo_unitario = 0.0 OR costo_unitario IS NULL) AND producto_id IS NOT NULL
        """)
        
        # Promociones / Combos
        cursor.execute("""
        UPDATE ventas_detalle
        SET costo_unitario = (
            SELECT COALESCE(SUM(p.costo_final * pd.cantidad_requerida), 0.0)
            FROM promocion_detalles pd
            JOIN productos p ON p.id = pd.producto_id
            WHERE pd.promocion_id = ventas_detalle.promocion_id
        )
        WHERE (costo_unitario = 0.0 OR costo_unitario IS NULL) AND promocion_id IS NOT NULL
        """)
    except Exception as e:
        print("Error al migrar costo_unitario histórico:", e)

    conn.commit()
    conn.close()
    
    # 3. Disparar backup automático silencioso
    auto_backup_db()

def auto_backup_db():
    import shutil
    import datetime
    
    # Carpeta de backups automáticos (junto a la DB original)
    backup_dir = DB_DIR / "Backups_Automaticos"
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    hoy = datetime.date.today()
    
    # Buscar si ya hay un backup reciente (menos de 7 días)
    necesita_backup = True
    for archivo in backup_dir.glob("backup_auto_*.sqlite"):
        try:
            # Extraer fecha del nombre: backup_auto_YYYY-MM-DD.sqlite
            fecha_str = archivo.stem.split("_")[-1]
            fecha_backup = datetime.datetime.strptime(fecha_str, "%Y-%m-%d").date()
            if (hoy - fecha_backup).days < 7:
                necesita_backup = False
                break
        except Exception:
            continue
            
    if necesita_backup:
        try:
            destino = backup_dir / f"backup_auto_{hoy.strftime('%Y-%m-%d')}.sqlite"
            shutil.copy2(DB_PATH, destino)
            
            # Limpieza: mantener solo los últimos 5 backups para no llenar el disco
            backups = sorted(backup_dir.glob("backup_auto_*.sqlite"))
            while len(backups) > 5:
                backups[0].unlink()
                backups.pop(0)
        except Exception as e:
            print(f"Error al generar backup automático: {e}")

if __name__ == "__main__":
    init_db()
    print(f"Base de datos inicializada en {DB_PATH}")
