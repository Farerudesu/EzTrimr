import sys
import os
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QByteArray, QRectF
from PyQt6.QtGui import QPixmap, QPainter, QColor
from PyQt6.QtSvg import QSvgRenderer
from PIL import Image

def main():
    # Setup PyQt Application context for QSvgRenderer & QPixmap
    app = QApplication(sys.argv)
    
    # Path setup
    root_dir = Path(__file__).resolve().parent.parent
    assets_dir = root_dir / "assets"
    assets_dir.mkdir(exist_ok=True)
    icon_path = assets_dir / "icon.ico"

    # SVG Scissors path data
    scissors_path = '<circle cx="4" cy="4" r="2.5"/><circle cx="4" cy="12" r="2.5"/><path d="M6 5.5L14 11M6 10.5L14 5"/>'
    
    # Render sizes
    sizes = [16, 32, 64, 128, 256]
    images = []

    for size in sizes:
        # Create a QPixmap for the background
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw background (#0078d4)
        painter.setBrush(QColor("#0078d4"))
        painter.setPen(Qt.PenStyle.NoPen)
        # Rounded rectangle
        radius = max(2, int(size * 0.12))
        painter.drawRoundedRect(0, 0, size, size, radius, radius)
        
        # Wrap the scissors path in SVG
        # We make the actual icon scale nicely, e.g. occupy 65% of center area
        icon_size = int(size * 0.65)
        offset = (size - icon_size) / 2
        
        # Design details: stroke-based white path
        svg_str = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="{icon_size}" height="{icon_size}" '
            f'fill="none" stroke="#ffffff" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
            f'{scissors_path}'
            f'</svg>'
        )
        
        renderer = QSvgRenderer(QByteArray(svg_str.encode('utf-8')))
        
        # Render centered
        rect = QRectF(offset, offset, icon_size, icon_size)
        renderer.render(painter, rect)
        painter.end()
        
        # Convert QPixmap to PIL Image via temp save
        temp_png = assets_dir / f"temp_{size}.png"
        pixmap.save(str(temp_png), "PNG")
        
        # Load with PIL
        pil_img = Image.open(temp_png)
        images.append(pil_img)

    # Save multi-size ICO
    images[0].save(
        str(icon_path),
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[1:]
    )
    print(f"Generated multi-size icon successfully at: {icon_path}")
    
    # Cleanup temp PNGs
    for size in sizes:
        temp_png = assets_dir / f"temp_{size}.png"
        try:
            pil_img = images[sizes.index(size)]
            pil_img.close()
            os.remove(temp_png)
        except Exception as e:
            print(f"Warning cleaning up {temp_png}: {e}")

if __name__ == "__main__":
    main()
