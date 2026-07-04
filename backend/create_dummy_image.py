import os
from PIL import Image

def generate_dummy_image(filename):
    # Create a 200x200 solid blue image
    img = Image.new('RGB', (200, 200), color=(59, 130, 246))
    img.save(filename)
    print(f"Saved dummy image to {filename}")

if __name__ == '__main__':
    generate_dummy_image('test_item.png')
