import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from dataclasses import replace
from pathlib import Path

import pytest
from PIL import Image
from preview_wait import wait_preview

from automatic_print.layout import LayoutSettings
from automatic_print.layout_engine.planner import plan_layout
from automatic_print.layout_engine.cut_validation import validate_cut_corridor, validate_canvas_pixels
from automatic_print.ui.pair_preview import PairProductionPreview
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage


def test_independent_validator_rejects_crossing_lower_row(tmp_path):
    paths = []
    for i in range(4):
        path = tmp_path / f"{i}.png"
        Image.new("RGBA", (100, 150), "blue").save(path, dpi=(25.4,25.4))
        paths.append(path)
    settings = LayoutSettings(dpi=25.4, cutter_mode="dual", number_images=False)
    planned, _, width, _, _ = plan_layout(paths, settings, None)
    check = validate_cut_corridor(planned, settings, width)
    assert check["checked_images"] == 4
    altered = list(planned)
    path, placement = altered[-1]
    altered[-1] = path, replace(placement, x_px=290)
    with pytest.raises(ValueError, match="图片进入整批切割安全通道"):
        validate_cut_corridor(altered, settings, width)


def test_pixel_validation_rejects_ink_at_end_of_canvas():
    canvas = Image.new("RGBA", (100, 1000))
    check = {"safe_left_px":40, "safe_right_px":60}
    canvas.putpixel((50,999), (0,0,0,255))
    with pytest.raises(ValueError, match="禁止保存"):
        validate_canvas_pixels(canvas, check)
    canvas.putpixel((50,999),(0,0,0,0))
    validate_canvas_pixels(canvas, check)
    assert check["pixel_verified"]


def test_overview_contains_whole_batch_without_loading_thumbnails(tmp_path):
    app = QApplication.instance() or QApplication([])
    for i in range(16):
        Image.new("RGBA", (100,150), "blue").save(tmp_path/f"{i:02}.png",dpi=(25.4,25.4))
    settings = LayoutSettings(dpi=100, cutter_mode="dual", number_images=False)
    preview = PairProductionPreview(lambda:settings)
    preview.resize(800,440)
    preview.overview = True
    preview.use_folder(str(tmp_path))
    wait_preview(preview)
    assert len(preview.planned) == 16
    assert preview.minimumHeight() > 440
    canvas = QImage(preview.size(), QImage.Format_ARGB32)
    canvas.fill(0)
    preview.render(canvas)
    assert preview.images == {}
    assert "整批轻量结构图" in preview.detail
    preview.close()
