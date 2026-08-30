from src.db.database import get_connection

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
        conn = get_connection()
        cursor = conn.cursor()
        try:
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
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
            UPDATE proveedores 
            SET nombre = ?, telefono = ?, direccion = ?
            WHERE id = ?
            """, (nombre, telefono, direccion, prov_id))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def eliminar_proveedor(prov_id):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE proveedores SET activo = 0 WHERE id = ?", (prov_id,))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
