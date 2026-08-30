from src.db.database import get_connection

class PromocionesManager:
    @staticmethod
    def get_all():
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM promociones WHERE activa = 1")
        promociones = cursor.fetchall()
        
        resultado = []
        for p in promociones:
            cursor.execute("SELECT producto_id, cantidad_requerida FROM promocion_detalles WHERE promocion_id = ?", (p['id'],))
            detalles = cursor.fetchall()
            
            resultado.append({
                'id': p['id'],
                'nombre': p['nombre'],
                'precio_fijo': p['precio_fijo'],
                'detalles': [{'producto_id': d['producto_id'], 'cantidad_requerida': d['cantidad_requerida']} for d in detalles]
            })
            
        conn.close()
        return resultado

    @staticmethod
    def crear_promocion(nombre, precio_fijo, detalles):
        # detalles es una lista de dicts: [{'producto_id': 1, 'cantidad_requerida': 1}, ...]
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO promociones (nombre, precio_fijo, activa) VALUES (?, ?, 1)", (nombre, precio_fijo))
            promo_id = cursor.lastrowid
            
            for d in detalles:
                cursor.execute("INSERT INTO promocion_detalles (promocion_id, producto_id, cantidad_requerida) VALUES (?, ?, ?)",
                               (promo_id, d['producto_id'], d['cantidad_requerida']))
            
            conn.commit()
            return promo_id
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def eliminar_promocion(promocion_id):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE promociones SET activa = 0 WHERE id = ?", (promocion_id,))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def actualizar_promocion(promocion_id, nombre, precio_fijo, detalles):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE promociones SET nombre = ?, precio_fijo = ? WHERE id = ?", 
                           (nombre, precio_fijo, promocion_id))
            
            cursor.execute("DELETE FROM promocion_detalles WHERE promocion_id = ?", (promocion_id,))
            
            for d in detalles:
                cursor.execute("INSERT INTO promocion_detalles (promocion_id, producto_id, cantidad_requerida) VALUES (?, ?, ?)",
                               (promocion_id, d['producto_id'], d['cantidad_requerida']))
            
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
