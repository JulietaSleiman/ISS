import sqlite3
import os
import random
from pathlib import Path
from src.core.caja_manager import CajaManager
from src.core.productos_manager import ProductosManager
from src.core.clientes_manager import ClientesManager
from src.core.promociones_manager import PromocionesManager
from src.db.database import init_db, get_connection, DB_PATH

def cargar_datos_prueba():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print("Base de datos anterior eliminada.")

    print("Inicializando BD nueva...")
    init_db()
    
    conn = get_connection()
    cursor = conn.cursor()
    
    print("Insertando Categorías y Proveedores...")
    categorias = ['Bebidas Sin Alcohol', 'Bebidas Con Alcohol', 'Golosinas', 'Snacks', 'Cigarrillos', 'Almacén', 'Lácteos']
    for i, cat in enumerate(categorias, 1):
        cursor.execute("INSERT OR IGNORE INTO categorias (id, nombre) VALUES (?, ?)", (i, cat))
        
    proveedores = ['Coca Cola', 'PepsiCo', 'Arcor', 'Massalin Particulares', 'Distribuidora Central', 'Cervecería Quilmes', 'La Serenísima']
    for i, prov in enumerate(proveedores, 1):
        cursor.execute("INSERT OR IGNORE INTO proveedores (id, nombre) VALUES (?, ?)", (i, prov))
        
    conn.commit()
    conn.close()

    print("Poblando Productos a escala real...")
    
    productos_datos = [
        # Bebidas Sin Alcohol
        ("77912341", "Coca Cola 2.25L", 1500, 2000, 1, 1),
        ("77912342", "Sprite 2.25L", 1400, 1900, 1, 1),
        ("77912343", "Fanta 2.25L", 1400, 1900, 1, 1),
        ("77912344", "Agua Kin 1.5L", 600, 900, 1, 1),
        ("77912345", "Gatorade Manzana 500ml", 800, 1200, 1, 2),
        ("77912346", "Pepsi 2.25L", 1350, 1800, 1, 2),
        ("77912347", "7Up 2.25L", 1350, 1800, 1, 2),
        ("77912348", "Paso de los Toros Pomelo 1.5L", 1100, 1500, 1, 2),
        
        # Bebidas Con Alcohol
        ("77920001", "Cerveza Quilmes Clásica 1L", 1200, 1700, 2, 6),
        ("77920002", "Cerveza Brahma 1L", 1100, 1600, 2, 6),
        ("77920003", "Cerveza Stella Artois 710ml", 1800, 2500, 2, 6),
        ("77920004", "Cerveza Patagonia Amber 730ml", 2200, 3100, 2, 6),
        ("77920005", "Fernet Branca 750ml", 6500, 8500, 2, 5),
        ("77920006", "Vino Toro Tinto 1L (Tetra)", 1000, 1400, 2, 5),
        ("77920007", "Vino Rutini Cabernet", 12000, 18000, 2, 5),
        ("77920008", "Vodka Smirnoff 700ml", 4500, 6000, 2, 5),
        
        # Golosinas
        ("77930001", "Alfajor Guaymallen Chocolate", 200, 350, 3, 5),
        ("77930002", "Alfajor Jorgito Dulce de Leche", 350, 600, 3, 5),
        ("77930003", "Alfajor Águila Minio", 500, 900, 3, 3),
        ("77930004", "Chocolate Block 170g", 1500, 2200, 3, 3),
        ("77930005", "Caramelos Sugus (Bolsa 100g)", 600, 1000, 3, 3),
        ("77930006", "Chicles Beldent Menta", 300, 500, 3, 5),
        ("77930007", "Chupetin Pico Dulce", 150, 250, 3, 5),
        ("77930008", "Rocklets 40g", 400, 700, 3, 3),
        
        # Snacks
        ("77940001", "Papas Lays Clásicas 145g", 1200, 1800, 4, 2),
        ("77940002", "Doritos Queso 100g", 1100, 1700, 4, 2),
        ("77940003", "Cheetos 90g", 900, 1400, 4, 2),
        ("77940004", "Palitos Pehuamar 150g", 800, 1300, 4, 2),
        ("77940005", "Maní King Salado 100g", 500, 850, 4, 5),
        ("77940006", "Tutucas (Bolsa grande)", 400, 700, 4, 5),
        
        # Cigarrillos
        ("77950001", "Marlboro Box 20", 2500, 2800, 5, 4),
        ("77950002", "Philip Morris Box 20", 2300, 2600, 5, 4),
        ("77950003", "Chesterfield KS 20", 2000, 2300, 5, 4),
        ("77950004", "Lucky Strike Box 20", 2200, 2500, 5, 5),
        ("77950005", "Camel Box 20", 2400, 2700, 5, 5),
        
        # Lácteos y Almacén
        ("77960001", "Leche Sachet La Serenísima 1L", 900, 1200, 7, 7),
        ("77960002", "Yogur Bebible Vainilla 1L", 1100, 1500, 7, 7),
        ("77960003", "Pan Bimbo Blanco", 1500, 2200, 6, 5),
        ("77960004", "Yerba Playadito 500g", 1600, 2300, 6, 5),
        ("77960005", "Azúcar Ledesma 1kg", 800, 1100, 6, 5)
    ]
    
    ids_productos = {}
    
    for p in productos_datos:
        cod, nom, costo, p_contado, cat_id, prov_id = p
        try:
            # utilidad es un calculo estimado aqui solo para llenar
            utilidad = ((p_contado - costo) / costo) * 100
            pid = ProductosManager.crear_producto(cod, nom, costo, 0, utilidad, random.randint(10, 100), 5, 100, cat_id, prov_id)
            ids_productos[nom] = pid
        except Exception as e:
            print(f"Error insertando {nom}: {e}")

    print(f"Se insertaron {len(ids_productos)} productos.")

    print("Insertando Promociones Realistas...")
    try:
        # PROMO 1: Fernet + 2 Cocas
        if "Fernet Branca 750ml" in ids_productos and "Coca Cola 2.25L" in ids_productos:
            detalles = [
                {'producto_id': ids_productos["Fernet Branca 750ml"], 'cantidad_requerida': 1},
                {'producto_id': ids_productos["Coca Cola 2.25L"], 'cantidad_requerida': 2}
            ]
            PromocionesManager.crear_promocion("Combo Fernet + 2 Cocas", 11500, detalles)

        # PROMO 2: 2x1 Cerveza Quilmes
        if "Cerveza Quilmes Clásica 1L" in ids_productos:
            detalles = [
                {'producto_id': ids_productos["Cerveza Quilmes Clásica 1L"], 'cantidad_requerida': 2}
            ]
            PromocionesManager.crear_promocion("2x Cerveza Quilmes 1L", 3000, detalles)

        # PROMO 3: Papas Lays + Cerveza Stella
        if "Papas Lays Clásicas 145g" in ids_productos and "Cerveza Stella Artois 710ml" in ids_productos:
            detalles = [
                {'producto_id': ids_productos["Papas Lays Clásicas 145g"], 'cantidad_requerida': 1},
                {'producto_id': ids_productos["Cerveza Stella Artois 710ml"], 'cantidad_requerida': 2}
            ]
            PromocionesManager.crear_promocion("Previa: Stellax2 + Lays", 6000, detalles)

        # PROMO 4: Desayuno (Leche + Pan)
        if "Leche Sachet La Serenísima 1L" in ids_productos and "Pan Bimbo Blanco" in ids_productos:
            detalles = [
                {'producto_id': ids_productos["Leche Sachet La Serenísima 1L"], 'cantidad_requerida': 1},
                {'producto_id': ids_productos["Pan Bimbo Blanco"], 'cantidad_requerida': 1}
            ]
            PromocionesManager.crear_promocion("Desayuno Completo", 3000, detalles)
            
        # PROMO 5: Promo Kiosco (3 Guaymallen)
        if "Alfajor Guaymallen Chocolate" in ids_productos:
            detalles = [
                {'producto_id': ids_productos["Alfajor Guaymallen Chocolate"], 'cantidad_requerida': 3}
            ]
            PromocionesManager.crear_promocion("Llevá 3 Guaymallen", 900, detalles)

    except Exception as e: 
        print(f"Error creando promos: {e}")

    print("Insertando Clientes de Prueba...")
    try:
        ClientesManager.crear_cliente("Juan Perez", "20304050607", "Calle Falsa 123", "Capital", "Tucuman", "Responsable Inscripto", "3811234567", "Cuenta Corriente", 5.0)
        ClientesManager.crear_cliente("María Gomez", "27405060708", "Av Aconquija 1000", "Yerba Buena", "Tucuman", "Consumidor Final", "3819876543", "Contado", 0.0)
    except Exception: pass

    print("Abriendo Caja Diaria...")
    try:
        CajaManager.abrir_caja(15000.0)
    except Exception as e:
        pass

    print("=======================================")
    print(" BASE DE DATOS POBLADA EXITOSAMENTE")
    print("=======================================")

if __name__ == "__main__":
    cargar_datos_prueba()
