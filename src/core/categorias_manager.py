from src.db.database import get_connection
from src.core.auth_manager import AuthManager
from src.core.entity_sync_store import EntitySyncStore

class CategoriasManager:
    @staticmethod
    def get_all():
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM categorias ORDER BY nombre ASC")
        categorias = cursor.fetchall()
        conn.close()
        return [dict(c) for c in categorias]

    @staticmethod
    def crear_categoria(nombre):
        user = AuthManager.require_user()
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('BEGIN IMMEDIATE')
            EntitySyncStore._bind(conn, user)
            cursor.execute("INSERT INTO categorias (nombre) VALUES (?)", (nombre,))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def actualizar_categoria(cat_id, nombre):
        user = AuthManager.require_user()
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('BEGIN IMMEDIATE')
            EntitySyncStore._bind(conn, user)
            previous = cursor.execute('SELECT nombre FROM categorias WHERE id = ?', (cat_id,)).fetchone()
            if previous is None:
                raise ValueError('No se encontró la categoría.')
            cursor.execute("UPDATE categorias SET nombre = ? WHERE id = ?", (nombre, cat_id))
            if previous['nombre'] != nombre:
                products = cursor.execute('SELECT id FROM productos WHERE categoria_id = ?', (cat_id,)).fetchall()
                for product in products:
                    EntitySyncStore.queue_product(conn, product['id'], user, catalog_changed=False)
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def eliminar_categoria(cat_id):
        user = AuthManager.require_user()
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('BEGIN IMMEDIATE')
            EntitySyncStore._bind(conn, user)
            # Eliminar solo si no está en uso
            cursor.execute("SELECT COUNT(*) as count FROM productos WHERE categoria_id = ?", (cat_id,))
            if cursor.fetchone()['count'] > 0:
                raise Exception("No se puede eliminar la categoría porque hay productos que la usan.")
            
            cursor.execute("DELETE FROM categorias WHERE id = ?", (cat_id,))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
