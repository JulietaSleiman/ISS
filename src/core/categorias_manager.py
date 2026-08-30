from src.db.database import get_connection

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
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO categorias (nombre) VALUES (?)", (nombre,))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def actualizar_categoria(cat_id, nombre):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE categorias SET nombre = ? WHERE id = ?", (nombre, cat_id))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def eliminar_categoria(cat_id):
        conn = get_connection()
        cursor = conn.cursor()
        try:
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
