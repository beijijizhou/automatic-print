"""Small, platform-independent vector icons; never depend on emoji fonts."""
from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication


PATHS = {
    'done': '<circle cx="12" cy="12" r="9"/><path d="m7 12 3 3 7-7"/>',
    'waiting': '<circle cx="12" cy="12" r="9"/><path d="M12 6v6l4 2"/>',
    'warning': '<path d="m12 3 10 18H2Z M12 9v5M12 17h.01"/>',
    'batch_single': '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 7h8M8 11h8m-5 4 4 2-4 2Z"/>',
    'batch_multiple': '<path d="M7 3h14v14M4 6h14v14"/><rect x="1" y="9" width="14" height="14" rx="2"/><path d="M5 13h6M5 17h6"/>',
    'zoom_in': '<circle cx="10" cy="10" r="7"/><path d="m15 15 6 6M6 10h8M10 6v8"/>',
    'zoom_out': '<circle cx="10" cy="10" r="7"/><path d="m15 15 6 6M6 10h8"/>',
    'expand': '<path d="M3 9V3h6M15 3h6v6M21 15v6h-6M9 21H3v-6"/>',
    'play': '<path d="m8 5 11 7-11 7Z"/>',
    'stop': '<rect x="6" y="6" width="12" height="12" rx="2"/>',
    'folder': '<path d="M3 7V5h6l2 2h10v13H3Z"/><path d="M3 10h18"/>',
    'preview': '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',
    'settings': '<path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="3"/><circle cx="15" cy="17" r="3"/>',
    'save': '<path d="M4 3h13l3 3v15H4Z"/><path d="M8 3v6h8V3M8 21v-8h8v8"/>',
    'refresh': '<path d="M20 9a8 8 0 0 0-14-3L3 9m0-5v5h5M4 15a8 8 0 0 0 14 3l3-3m0 5v-5h-5"/>',
    'copy': '<rect x="8" y="8" width="12" height="13" rx="2"/><path d="M15 8V3H3v13h5"/>',
    'text': '<path d="M4 5h16M12 5v15M8 20h8"/>',
    'color': '<rect x="4" y="4" width="16" height="16" rx="3"/><path d="m4 16 12-12M10 20 20 10"/>',
    'date': '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4M17 3v4M3 10h18M7 14h3M14 14h3"/>',
    'left': '<path d="M4 10a8 8 0 1 1 1 8M4 4v6h6"/>',
    'right': '<path d="M20 10a8 8 0 1 0-1 8M20 4v6h-6"/>',
    'machine': '<rect x="3" y="7" width="18" height="10" rx="2"/><path d="M7 7V3h10v4M7 17v4h10v-4M17 11h1"/>',
    'more': '<path d="M5 6h14M5 12h14M5 18h14"/>',
}

_ICON_CACHE = {}
_APP_TOKEN = None


def action_icon(name, color='#475569'):
    global _APP_TOKEN
    token = id(QApplication.instance())
    if token != _APP_TOKEN:
        _ICON_CACHE.clear()
        _APP_TOKEN = token
    key = name, color
    if key in _ICON_CACHE:
        return QIcon(_ICON_CACHE[key])
    icon = QIcon()
    for mode, stroke in ((QIcon.Normal, color), (QIcon.Disabled, '#94a3b8')):
        svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><g fill="none" stroke="{stroke}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{PATHS[name]}</g></svg>'
        pixmap = QPixmap(48, 48)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        try:
            QSvgRenderer(QByteArray(svg.encode())).render(painter)
        finally:
            painter.end()
        pixmap.setDevicePixelRatio(2)
        icon.addPixmap(pixmap, mode)
    _ICON_CACHE[key] = icon
    return QIcon(icon)
