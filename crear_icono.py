import os
from PIL import Image

try:
    src = 'logo.png' if os.path.exists('logo.png') else 'logo.jpg'
    img = Image.open(src).convert('RGBA')
    max_dim = max(img.size)
    square_icon = Image.new('RGBA', (max_dim, max_dim), (0, 0, 0, 0))
    square_icon.paste(img, ((max_dim - img.width) // 2, (max_dim - img.height) // 2))
    square_icon.save('logo.ico', format='ICO', sizes=[(16,16), (32,32), (48,48), (64,64), (128,128), (256,256)])
    print("Icono multi-resolución creado exitosamente.")
except Exception as e:
    print(f"Error: {e}")
