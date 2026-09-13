from dataclasses import replace

from PIL.ImageQt import ImageQt
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage, QImageReader

from ..layout_engine.dynamic_label import source_label_badge
from ..layout_engine.models import mm_to_px
from ..layout_engine.transition_marks import marked_height, transition_rects


def install_snapshot(preview, planned, labels, settings, warning="", overflow=()):
    images, badges = {}, {}
    top = min(p.row_y_px for _, p in planned)
    local = [(path, replace(p, y_px=p.y_px-top, number_y_px=p.number_y_px-top,
                            color_block_y_px=p.color_block_y_px-top, row_y_px=p.row_y_px-top,
                            platform_y_px=p.platform_y_px-top))
             for path, p in planned]
    for path, p in local:
        if getattr(preview, "overview", False):
            continue
        image = preview.images.get(path, QImage())
        if image.isNull():
            reader = QImageReader(str(path))
            size = reader.size()
            if size.isValid():
                reader.setScaledSize(size.scaled(QSize(900, 900), Qt.KeepAspectRatio))
            image = reader.read()
        if image.isNull():
            raise ValueError(f"无法读取 {path.name}")
        images[path] = image
        if settings.number_images and p.number_width_px:
            badge = source_label_badge(labels[p.sequence_number], settings, path, p.rotation_degrees)
            badges[path] = QImage(ImageQt(badge)).copy()
            badge.close()
    preview.images, preview.badges, preview.planned = images, badges, local
    preview.platform_badges = {}
    preview.item = local[0][1]
    preview.film_width = mm_to_px(settings.media_width_mm, settings.dpi)
    preview.canvas_width = max(preview.film_width, max(p.x_px+p.width_px for _, p in local))
    preview.canvas_height = max(p.row_y_px+p.footprint_height_px for _, p in local)
    if getattr(preview, 'overview', False) or not preview.batch_payload:
        preview.canvas_height = marked_height(local, settings, preview.canvas_width, preview.canvas_height)
    elif settings.transition_lines:
        full = preview.batch_payload['planned']
        limit = top+preview.canvas_height+mm_to_px(settings.transition_gap_mm, settings.dpi)+1
        notices = [r['y']-top+r['height'] for r in transition_rects(full, settings, preview.canvas_width)
                   if top <= r['y'] <= limit]
        preview.canvas_height = max([preview.canvas_height]+notices)
    preview.render_settings, preview.warning = settings, warning
    preview.batch_labels = labels
    preview.overflow = [(x, y-top, w, h) for x, y, w, h in overflow]
    if getattr(preview, "overview", False):
        preview.setMinimumHeight(max(440, round(preview.canvas_height *
                                 max(400, preview.width()-32)/preview.canvas_width)+110))
    else:
        preview.setMinimumHeight(440)
    if hasattr(preview, 'view_controls'):
        preview.view_controls.update_geometry()
