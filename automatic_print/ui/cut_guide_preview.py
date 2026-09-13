"""Draw dotted knife indicators only alongside actual QR height bands."""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPen

from ..layout_engine.cut_guide_geometry import guide_spans
from ..layout_engine.printed_guides import dot_boxes


def draw_cut_guides(preview, painter, scale):
    if preview.render_settings.cutter_mode != 'dual':
        preview.guide_status = ''
        return
    visible = [(path, p) for path, p in preview.planned if painter.clipBoundingRect().intersects(
        QRectF(0, p.y_px, preview.canvas_width, p.height_px))]
    bands, missing, waiting = preview.cut_guides.request([path for path, _ in visible])
    spans = guide_spans(visible, preview.render_settings, bands)
    preview.guide_status = '红色刀位点线会写入输出图片，仅限二维码高度范围'
    if waiting:
        preview.guide_status += f' · 正在识别 {len(waiting)} 张可见图片的二维码'
    if missing:
        preview.guide_status += f' · {len(missing)} 张未识别二维码，未猜测点线范围'
    painter.save()
    try:
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor('#ff0000'))
        for x, y, diameter in dot_boxes(spans, preview.render_settings.dpi):
            painter.drawEllipse(QRectF(x, y, diameter, diameter))
        painter.setPen(QPen(QColor('#ff0000'), 0))
        _zone_boundary(preview, painter, scale)
    finally:
        painter.restore()


def _zone_boundary(preview, painter, scale):
    # Keep the change-of-knife annotation in the blank gap before the rotated zone.
    normal = [p for _, p in preview.planned if p.cut_zone == '常规区']
    rotated = [p for _, p in preview.planned if p.cut_zone == '旋转区']
    if not normal or not rotated:
        return
    bottom = max(p.row_y_px+p.footprint_height_px for p in normal)
    top = min(p.row_y_px for p in rotated)
    if (top-bottom)*scale < 14:
        return
    painter.setClipRect(QRectF(0, bottom, preview.film_width, top-bottom))
    font = painter.font()
    font.setPixelSize(max(1, round(12/scale)))
    painter.setFont(font)
    knife = rotated[0].cut_knife_x_px
    painter.drawText(QRectF(6/scale, bottom, preview.film_width, top-bottom),
                     f'进入旋转区 · 在此换刀 · 刀位 {knife*25.4/preview.render_settings.dpi:.1f} 毫米')
