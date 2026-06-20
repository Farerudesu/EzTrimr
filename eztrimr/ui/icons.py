import os
from PyQt6.QtCore import Qt, QByteArray, QBuffer
from PyQt6.QtGui import QIcon, QPixmap, QColor, QPainter
from PyQt6.QtSvg import QSvgRenderer

SVG_ICONS = {
    "folder-open": '<path d="M1.5 3.5h3l1.5 1.5h6.5v8.5h-11v-10z"/><path d="M1.5 6h11l1.5 6h-11.5z"/>',
    "plus": '<path d="M8 2v12M2 8h12"/>',
    "download": '<path d="M8 2v9m-3-3l3 3 3-3M2 14h12"/>',
    "scissors": '<circle cx="4" cy="4" r="2.5"/><circle cx="4" cy="12" r="2.5"/><path d="M6 5.5L14 11M6 10.5L14 5"/>',
    "merge": '<path d="M2 3h4l5 5h3M2 13h4l5-5"/>',
    "trash": '<path d="M3 3h10M4 3v10a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V3M6 3V1.5a.5.5 0 0 1 .5-.5h3a.5.5 0 0 1 .5.5V3M6 6v5M10 6v5M8 6v5"/>',
    "arrow-up": '<path d="M2 11l6-6 6 6"/>',
    "arrow-down": '<path d="M2 5l6 6 6-6"/>',
    "play": '<path d="M4 2.5l9 5.5-9 5.5v-11z"/>',
    "waveform": '<path d="M3 5v6M8 2v12M13 4v8"/>',
    "settings": '<circle cx="8" cy="8" r="3"/><path d="M8 1v2M8 13v2M1 8h2M13 8h2M3.05 3.05l1.41 1.41M11.54 11.54l1.41 1.41M3.05 12.95l1.41-1.41M11.54 4.46l1.41-1.41"/>',
    "info": '<circle cx="8" cy="8" r="7"/><path d="M8 11V7M8 5h.01"/>',
    "warning": '<path d="M8 1.5l7 12H1z"/><path d="M8 5v4M8 11.5h.01"/>',
    "check": '<path d="M2.5 8.5l3.5 3.5 7.5-7.5"/>',
    "close": '<path d="M3 3l10 10M13 3L3 13"/>',
    "export": '<path d="M6 2H2a1 1 0 0 0-1 1v11a1 1 0 0 0 1 1h11a1 1 0 0 0 1-1v-4M9 1h6v6M15 1L7.5 8.5"/>',
    "audio-mute": '<path d="M1 5h3l3.5-3.5v13L4 11H1zM10.5 5.5l3 5M13.5 5.5l-3 5"/>',
    "normalize": '<path d="M1 8h14M3 5v6M6 3v10M9 6v4M12 4v8"/>',
    "film": '<rect x="1.5" y="1.5" width="13" height="13" rx="1.5"/><path d="M4.5 1.5v13M11.5 1.5v13M1.5 4.5h3M11.5 4.5h3M1.5 8h3M11.5 8h3M1.5 11.5h3M11.5 11.5h3"/>',
    "keyboard": '<rect x="1.5" y="3.5" width="13" height="9" rx="1"/><path d="M4.5 6.5h1M7.5 6.5h1M10.5 6.5h1M3.5 9.5h9"/>',
}

class EZIcon:
    _cache = {}

    @staticmethod
    def get(name: str, size: int = 16, color: QColor | None = None) -> QPixmap:
        from eztrimr.ui.theme import get_token
        if color is None:
            color = get_token("text_primary")
            
        color_hex = color.name()
        
        # Check cache
        cache_key = (name, size, color_hex)
        if cache_key in EZIcon._cache:
            return EZIcon._cache[cache_key]
            
        path_data = SVG_ICONS.get(name, "")
        fill_val = color_hex if name == "play" else "none"
        
        # SVG envelope designed at 16x16 viewBox, stroke-based (except play filled)
        svg_str = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="{size}" height="{size}" '
            f'fill="{fill_val}" stroke="{color_hex}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
            f'{path_data}'
            f'</svg>'
        )
        
        renderer = QSvgRenderer(QByteArray(svg_str.encode('utf-8')))
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        
        EZIcon._cache[cache_key] = pixmap
        return pixmap

    @staticmethod
    def icon(name: str, size: int = 16, color: QColor | None = None) -> QIcon:
        pixmap_normal = EZIcon.get(name, size, color)
        
        # Disabled state uses text_muted color
        from eztrimr.ui.theme import get_token
        muted_color = get_token("text_muted")
        pixmap_disabled = EZIcon.get(name, size, muted_color)
        
        icon = QIcon()
        icon.addPixmap(pixmap_normal, QIcon.Mode.Normal, QIcon.State.Off)
        icon.addPixmap(pixmap_normal, QIcon.Mode.Normal, QIcon.State.On)
        icon.addPixmap(pixmap_disabled, QIcon.Mode.Disabled, QIcon.State.Off)
        icon.addPixmap(pixmap_disabled, QIcon.Mode.Disabled, QIcon.State.On)
        return icon

    @staticmethod
    def to_base64_img(name: str, size: int = 16, color: QColor | None = None) -> str:
        pixmap = EZIcon.get(name, size, color)
        byte_array = QByteArray()
        buffer = QBuffer(byte_array)
        buffer.open(QBuffer.OpenModeFlag.WriteOnly)
        pixmap.save(buffer, "PNG")
        buffer.close()
        b64 = byte_array.toBase64().data().decode("utf-8")
        return f'<img src="data:image/png;base64,{b64}" width="{size}" height="{size}" />'
