import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from PIL import Image
from PySide6.QtGui import QImage, QPainter
import pytest

from automatic_print.layout import LayoutSettings
from automatic_print.layout_engine.models import Placement
from automatic_print.ui.cut_guide_preview import _transition_lines
from automatic_print.layout_engine.marked_pixel_validation import validate_marked_pillow
from automatic_print.layout_engine.printed_guides import vips_corridor_is_clear


def test_preview_uses_real_batch_not_selected_picture_end():
    p = Placement('a.png', 1, 15, 10, 100, 80, 0, 0, 0, 0, 10, 115, 80, cut_zone='常规区')
    q = replace(p, source='b.png', sequence_number=2, row_y_px=110, y_px=110, height_px=90,
                footprint_height_px=90, cut_zone='旋转区')
    planned = [(Path('a.png'), p), (Path('b.png'), q)]
    preview = SimpleNamespace(render_settings=LayoutSettings(dpi=25.4, transition_lines=True),
        batch_payload={'planned': planned}, canvas_width=600,
        planned=[(path, replace(row, row_y_px=row.row_y_px-10, y_px=row.y_px-10)) for path, row in planned])
    image = QImage(600, 205, QImage.Format_RGBA8888)
    image.fill(0)
    painter = QPainter(image)
    try:
        _transition_lines(preview, painter)
    finally:
        painter.end()
    for y in (193,):
        assert image.pixelColor(0, y).getRgb() == (255, 0, 0, 255)
        assert image.pixelColor(599, y).getRgb() == (255, 0, 0, 255)
    assert image.pixelColor(0, 82).alpha() == 0
    assert image.pixelColor(0, 83).alpha() == 0


def test_exact_horizontal_mask_does_not_allow_extra_pixels():
    rects = [{'x': 0, 'y': 30, 'width': 100, 'height': 1}]
    check = {'safe_left_px': 47, 'safe_right_px': 53}
    image = Image.new('RGBA', (100, 60))
    for x in range(100):
        image.putpixel((x, 30), (255, 0, 0, 255))
    validate_marked_pillow(image, check, rectangles=rects)
    pyvips = pytest.importorskip('pyvips')
    marked = pyvips.Image.new_from_memory(image.tobytes(), 100, 60, 4, 'uchar').copy(interpretation='srgb')
    assert vips_corridor_is_clear(marked, check, rectangles=rects)
    image.putpixel((50, 31), (255, 0, 0, 255))
    with pytest.raises(ValueError, match='禁止输出'):
        validate_marked_pillow(image, check, rectangles=rects)
    extra = marked.draw_rect([255, 0, 0, 255], 50, 31, 1, 1, fill=True)
    assert not vips_corridor_is_clear(extra, check, rectangles=rects)


def test_preview_prints_footer_and_keeps_end_line_after_it():
    from PySide6.QtWidgets import QApplication
    from automatic_print.layout_engine.transition_marks import transition_rects, marked_height
    app = QApplication.instance() or QApplication([])
    p = Placement('B1-1-T-Black-M-NO1-1.png', 1, 0, 0, 100, 80,
                  0, 0, 0, 0, 0, 100, 80)
    planned = [(Path('batch')/p.source, p)]
    settings = LayoutSettings(dpi=25.4, transition_lines=True, transition_gap_mm=10,
                              batch_footer_enabled=True, batch_footer_font_mm=8)
    footer, line = transition_rects(planned, settings, 300)
    preview = SimpleNamespace(render_settings=settings, batch_payload={'planned':planned},
                              canvas_width=300, planned=planned)
    height = marked_height(planned, settings, 300, 80)
    image = QImage(300, height, QImage.Format_RGBA8888)
    image.fill(0)
    painter = QPainter(image)
    try:
        _transition_lines(preview, painter)
    finally:
        painter.end()
    assert any(image.pixelColor(x,y).alpha() for y in range(footer['y'], footer['y']+footer['height'])
               for x in range(footer['width']))
    assert image.pixelColor(0,line['y']).getRgb() == (255,0,0,255)
    assert image.pixelColor(0,line['y']-1).alpha() == 0
