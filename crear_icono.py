from PIL import Image
import sys

try:
    img = Image.open('logo.jpg')
    img.save('logo.ico')
    print("Icono creado exitosamente.")
except Exception as e:
    print(f"Error: {e}")
