from PIL import Image, ImageDraw
import math

# Create a 32x32 image with transparent background
img = Image.new('RGBA', (32, 32), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Draw concentric circles in green
center = (16, 16)
for r in range(14, 2, -4):
    draw.ellipse([center[0]-r, center[1]-r, center[0]+r, center[1]-r+2*r], 
                 outline=(0, 255, 0, 255))

# Save as ICO
img.save('static/favicon.ico', format='ICO') 