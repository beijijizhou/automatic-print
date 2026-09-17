from PIL.ImageQt import ImageQt
from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage, QFont, QColor, QPen

from ..layout_engine.platform_label import placement_badge, platform_text


def draw_platform_badge(preview, painter, placement, path):
    if not placement.platform_width_px:
        return
    cache = preview.platform_badges
    key = (
        platform_text(path, preview.render_settings),
        placement.platform_width_px,
        placement.platform_height_px,
        placement.rotation_degrees,
    )
    if key not in cache:
        badge = placement_badge(*key)
        cache[key] = QImage(ImageQt(badge)).copy()
        badge.close()
        while len(cache) > 12:
            cache.pop(next(iter(cache)))
    painter.drawImage(QRectF(placement.platform_x_px, placement.platform_y_px,
                            placement.platform_width_px, placement.platform_height_px), cache[key])


def draw_platform_diagram(preview, painter, image):
    # This low-cost settings diagram mirrors the production relationship:
    # QR and platform badge share the source header, never the cutter lane.
    card = QRectF(image.left()+8, image.top()+8, min(150, image.width()-16), 42)
    painter.fillRect(card, QColor('white'))
    qr = QRectF(card.left()+5, card.top()+5, 32, 32)
    draw_qr(painter, qr)
    painter.save()
    font = QFont()
    height_mm = preview.values().get('platform_font_height_mm', 0)
    font.setPixelSize(max(2, round(32*min(1, height_mm/10))) if height_mm else 32)
    font.setBold(True)
    painter.setFont(font)
    painter.setPen(QColor('black'))
    painter.drawText(QRectF(qr.right()+6, qr.top(), card.right()-qr.right()-10, qr.height()),
                     preview.values()['platform_name']+' · M')
    painter.restore()


def draw_qr(painter, rect):
    painter.setPen(QPen(QColor('#111827'), 1))
    painter.setBrush(QColor('#ffffff'))
    painter.drawRect(rect)
    painter.setBrush(QColor('#111827'))
    size = rect.width() / 5
    for column, row in ((0, 0), (3, 0), (0, 3), (2, 2), (4, 4)):
        painter.drawRect(QRectF(rect.left() + column * size,
                               rect.top() + row * size, size, size))
