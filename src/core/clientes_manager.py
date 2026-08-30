from src.db.database import get_connection

class ClientesManager:
    @staticmethod
    def get_all():
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM clientes WHERE activo = 1 ORDER BY nombre ASC")
        clientes = cursor.fetchall()
        conn.close()
        return [dict(c) for c in clientes]

    @staticmethod
    def get_by_id(cliente_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM clientes WHERE id = ? AND activo = 1", (cliente_id,))
        cliente = cursor.fetchone()
        conn.close()
        return dict(cliente) if cliente else None

    @staticmethod
    def crear_cliente(nombre, cuit, domicilio, localidad, provincia, condicion_iva, telefono, condicion_pago, descuento_porcentaje):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
            INSERT INTO clientes (nombre, cuit, domicilio, localidad, provincia, condicion_iva, telefono, condicion_pago, descuento_porcentaje, activo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """, (nombre, cuit, domicilio, localidad, provincia, condicion_iva, telefono, condicion_pago, descuento_porcentaje))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def actualizar_cliente(cliente_id, nombre, cuit, domicilio, localidad, provincia, condicion_iva, telefono, condicion_pago, descuento_porcentaje):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
            UPDATE clientes 
            SET nombre=?, cuit=?, domicilio=?, localidad=?, provincia=?, condicion_iva=?, telefono=?, condicion_pago=?, descuento_porcentaje=?
            WHERE id = ?
            """, (nombre, cuit, domicilio, localidad, provincia, condicion_iva, telefono, condicion_pago, descuento_porcentaje, cliente_id))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def eliminar_cliente(cliente_id):
        if cliente_id == 1:
            raise Exception("No se puede eliminar el Consumidor Final.")
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE clientes SET activo = 0 WHERE id = ?", (cliente_id,))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
