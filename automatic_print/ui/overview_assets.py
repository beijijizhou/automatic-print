from PIL.ImageQt import ImageQt
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage, QImageReader

from ..layout_engine.dynamic_label import source_label_badge


def visible_assets(preview, path, placement):
    if path not in preview.images:
        reader = QImageReader(str(path))
        size = reader.size()
        if size.isValid():
            controls = getattr(preview, 'view_controls', None)
            limit = min(1600, max(320, round(320*controls.zoom.value()/100))) if controls else 320
            reader.setScaledSize(size.scaled(QSize(limit, limit), Qt.KeepAspectRatio))
        preview.images[path] = reader.read()
        if placement.number_width_px:
            badge = source_label_badge(preview.batch_labels[placement.sequence_number],
                                       preview.render_settings, path, placement.rotation_degrees)
            preview.badges[path] = QImage(ImageQt(badge)).copy()
            badge.close()
    # Bounded cache: scrolling a large batch never retains all its thumbnails.
    while len(preview.images) > 12:
        old = next(iter(preview.images))
        if old == path:
            break
        preview.images.pop(old, None)
        preview.badges.pop(old, None)
    return preview.images[path]
