"""GUI-only dimension overlay; never used by production PNG rendering."""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen


def annotated_example(image, data, settings):
    item = data['item']
    top = min(0, item.block_ry)
    scale = min(900/item.footprint_width, 650/(item.footprint_height-top))
    left, above, below = 100, 100, 55
    result = QImage(image.width()+left+35, image.height()+above+below, QImage.Format_RGBA8888)
    result.fill(QColor('#f8fafc'))
    painter = QPainter(result)
    try:
        painter.setRenderHint(QPainter.Antialiasing)
        painter.drawImage(left, above, image)
        font = QFont()
        font.setPixelSize(20)
        painter.setFont(font)
        ix, iy = left+item.image_rx*scale, above+(item.image_ry-top)*scale
        bx, by = left+item.block_rx*scale, above+(item.block_ry-top)*scale
        edge = bx+item.block_width*scale
        painter.setPen(QPen(QColor('#2563eb'), 2, Qt.DashLine))
        painter.drawRect(QRectF(ix, iy, item.width*scale, item.height*scale))
        painter.setPen(QPen(QColor('#dc2626'), 2))
        painter.drawRect(QRectF(bx, by, item.block_width*scale, item.block_height*scale))
        painter.setPen(QPen(QColor('#64748b'), 1, Qt.DashLine))
        painter.drawLine(QPointF(25, by), QPointF(bx, by))
        painter.drawLine(QPointF(25, iy), QPointF(ix, iy))
        painter.drawLine(QPointF(edge, 65), QPointF(edge, by))
        painter.drawLine(QPointF(ix, 65), QPointF(ix, iy))
        painter.setPen(QPen(QColor('#c2410c'), 2))
        painter.drawLine(QPointF(edge, 70), QPointF(ix, 70))
        for x in (edge, ix):
            painter.drawLine(QPointF(x, 64), QPointF(x, 76))
        painter.drawLine(QPointF(35, by), QPointF(35, iy))
        for y in (by, iy):
            painter.drawLine(QPointF(29, y), QPointF(41, y))
        gap = (item.image_rx-item.block_rx-item.block_width)*25.4/settings.dpi
        lift = (item.image_ry-item.block_ry)*25.4/settings.dpi
        painter.drawText(QRectF(15, 10, result.width()-30, 50), Qt.AlignCenter,
                         f'水平间隙 {gap:.1f}毫米   ·   刀码抬高 {lift:.1f}毫米')
        painter.setPen(QColor('#475569'))
        painter.drawText(QRectF(10, result.height()-50, result.width()-20, 45), Qt.AlignCenter,
                         '蓝虚线：原图边界   红框：刀码   橙线：相对距离（仅预览）')
    finally:
        painter.end()
    return result
