from src.db.database import get_connection
from src.core.auth_manager import AuthManager
from src.core.entity_sync_store import EntitySyncStore

class ProveedoresManager:
    @staticmethod
    def get_all():
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM proveedores WHERE activo = 1 ORDER BY nombre ASC")
        proveedores = cursor.fetchall()
        conn.close()
        return [dict(p) for p in proveedores]

    @staticmethod
    def crear_proveedor(nombre, telefono, direccion):
        user = AuthManager.require_user()
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('BEGIN IMMEDIATE')
            EntitySyncStore._bind(conn, user)
            cursor.execute("""
            INSERT INTO proveedores (nombre, telefono, direccion, activo)
            VALUES (?, ?, ?, 1)
            """, (nombre, telefono, direccion))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def actualizar_proveedor(prov_id, nombre, telefono, direccion):
        user = AuthManager.require_user()
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('BEGIN IMMEDIATE')
            EntitySyncStore._bind(conn, user)
            previous = cursor.execute('SELECT nombre FROM proveedores WHERE id = ?', (prov_id,)).fetchone()
            if previous is None:
                raise ValueError('No se encontró el proveedor.')
            cursor.execute("""
            UPDATE proveedores 
            SET nombre = ?, telefono = ?, direccion = ?
            WHERE id = ?
            """, (nombre, telefono, direccion, prov_id))
            if previous['nombre'] != nombre:
                products = cursor.execute('SELECT id FROM productos WHERE proveedor_id = ?', (prov_id,)).fetchall()
                for product in products:
                    EntitySyncStore.queue_product(conn, product['id'], user, catalog_changed=False)
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def eliminar_proveedor(prov_id):
        user = AuthManager.require_user()
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('BEGIN IMMEDIATE')
            EntitySyncStore._bind(conn, user)
            cursor.execute("UPDATE proveedores SET activo = 0 WHERE id = ?", (prov_id,))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
