from PIL.ImageQt import ImageQt
from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage, QFont, QColor

from ..layout_engine.platform_label import platform_badge


def draw_platform_badge(preview, painter, placement):
    if not placement.platform_width_px:
        return
    cache = preview.platform_badges
    key = (preview.render_settings.platform_name, placement.platform_height_px)
    if key not in cache:
        badge = platform_badge(*key)
        cache[key] = QImage(ImageQt(badge)).copy()
        badge.close()
        while len(cache) > 12:
            cache.pop(next(iter(cache)))
    painter.drawImage(QRectF(placement.platform_x_px, placement.platform_y_px,
                            placement.platform_width_px, placement.platform_height_px), cache[key])


def draw_platform_diagram(preview, painter, image):
    qr = QRectF(image.right()-44, image.top()+12, 32, 32)
    preview._draw_qr(painter, qr)
    painter.save()
    font = QFont()
    font.setPixelSize(32)
    font.setBold(True)
    painter.setFont(font)
    painter.setPen(QColor('black'))
    painter.drawText(QRectF(image.right()+4, qr.top(), 100, qr.height()),
                     preview.values()['platform_name'])
    painter.restore()
