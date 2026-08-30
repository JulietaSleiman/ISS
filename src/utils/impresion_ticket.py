from datetime import datetime

class ImpresoraTicket:
    """
    Gestor de impresión para tickets térmicos de 80mm.
    (80mm permite aprox. 48 caracteres de ancho)
    """
    ANCHO_LINEA = 48

    @staticmethod
    def centrar(texto):
        return texto.center(ImpresoraTicket.ANCHO_LINEA)

    @staticmethod
    def alinear_derecha(texto):
        return texto.rjust(ImpresoraTicket.ANCHO_LINEA)

    @staticmethod
    def linea_separadora():
        return "-" * ImpresoraTicket.ANCHO_LINEA

    @staticmethod
    def generar_texto_ticket(venta_id, carrito, subtotal, descuento, total, paga_con="EFECTIVO", empresa_nombre="DRUGSTORE ARGENTINA"):
        lineas = []
        
        # Header
        lineas.append(ImpresoraTicket.centrar(empresa_nombre))
        lineas.append(ImpresoraTicket.centrar("CUIT: 30-12345678-9"))
        lineas.append(ImpresoraTicket.centrar("IVA Responsable Inscripto"))
        lineas.append(ImpresoraTicket.linea_separadora())
        
        # Datos de Venta
        fecha = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        lineas.append(f"Ticket Nro: {venta_id:08d}")
        lineas.append(f"Fecha: {fecha}")
        lineas.append(ImpresoraTicket.linea_separadora())
        
        # Cabecera Productos (Cant | Descripción | Importe)
        lineas.append("CANT DESCRIPCION                     IMPORTE")
        
        # Productos
        for item in carrito:
            cant_desc = f"{item['cantidad']} x {item['nombre'][:25]}"
            importe = f"${item['cantidad'] * item['precio_unitario']:.2f}"
            
            # Ajustar espacios para alinear a la derecha el importe
            espacios = ImpresoraTicket.ANCHO_LINEA - len(cant_desc) - len(importe)
            if espacios < 1: espacios = 1
            lineas.append(cant_desc + (" " * espacios) + importe)
        
        lineas.append(ImpresoraTicket.linea_separadora())
        
        # Totales
        if descuento > 0:
            lineas.append(ImpresoraTicket.alinear_derecha(f"Subtotal: ${subtotal:.2f}"))
            lineas.append(ImpresoraTicket.alinear_derecha(f"Descuento: -${descuento:.2f}"))
            
        lineas.append(ImpresoraTicket.alinear_derecha(f"TOTAL: ${total:.2f}"))
        lineas.append(ImpresoraTicket.linea_separadora())
        
        lineas.append(ImpresoraTicket.centrar(f"Medio de Pago: {paga_con}"))
        lineas.append(ImpresoraTicket.centrar("*** GRACIAS POR SU COMPRA ***"))
        
        return "\n".join(lineas)

    @staticmethod
    def imprimir(venta_id, carrito, subtotal, descuento, total, empresa_nombre="DRUGSTORE ARGENTINA"):
        """Envía el texto generado a la impresora por defecto de Windows."""
        texto = ImpresoraTicket.generar_texto_ticket(venta_id, carrito, subtotal, descuento, total, empresa_nombre=empresa_nombre)
        
        # Para Windows, se puede usar win32print (requiere pywin32) o enviar el archivo al puerto raw.
        # Por ahora lo guardamos en un archivo de log y lo mostramos por consola.
        print("\n--- TICKET GENERADO ---")
        print(texto)
        print("-----------------------\n")
        
        # TODO: Implementar envío físico a impresora térmica (ej. con python-escpos o win32print)
        return True
