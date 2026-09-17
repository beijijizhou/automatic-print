import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from automatic_print.layout_engine import LayoutSettings
from automatic_print.ui.pair_preview import PairProductionPreview
from dataclasses import replace
from preview_wait import wait_preview
from automatic_print.layout_engine.planning.base.planner import plan_layout


def test_two_image_preview_uses_fixed_partition_marker_groups(tmp_path):
    app = QApplication.instance() or QApplication([])
    for i in range(2):
        Image.new("RGBA", (180, 250), (0, 0, 255, 255)).save(tmp_path / f"{i}.png", dpi=(25.4, 25.4))
    settings = LayoutSettings(media_width_mm=600, dpi=100, cutter_mode="dual",
                              label_detect_region=True, label_text_template="CY M1 26")
    preview = PairProductionPreview(lambda: settings)
    preview.use_folder(str(tmp_path))
    wait_preview(preview)
    assert len(preview.planned) == 2
    left, right = [p for _, p in preview.planned]
    assert left.row_y_px == right.row_y_px
    assert left.color_block_x_px == 0
    assert right.color_block_x_px == round(303 * 100 / 25.4)
    for p in (left, right):
        assert p.number_x_px == p.color_block_x_px
        assert p.number_y_px >= p.color_block_y_px + p.color_block_height_px
    preview.resize(960, 620)
    canvas = QImage(preview.size(), QImage.Format_ARGB32)
    canvas.fill(0)
    preview.render(canvas)
    assert not canvas.isNull()
    preview.close()


def test_narrow_media_recovers_and_keeps_both_sources_in_batch_preview(tmp_path):
    app = QApplication.instance() or QApplication([])
    for i in range(2):
        Image.new("RGBA", (180, 250), "blue").save(tmp_path / f"{i}.png", dpi=(25.4, 25.4))
    state = [LayoutSettings(media_width_mm=600, dpi=100, cutter_mode="dual")]
    preview = PairProductionPreview(lambda: state[0])
    preview.use_folder(str(tmp_path))
    wait_preview(preview)
    assert not preview.warning
    state[0] = replace(state[0], media_width_mm=300, cutter_knife_mm=150)
    preview.refresh()
    wait_preview(preview)
    assert len(preview.batch_payload["planned"]) == 2
    assert all(p.rotation_degrees == 90 for _, p in preview.batch_payload["planned"])
    assert preview.item is not None
    assert not preview.overflow
    assert not preview.warning
    assert len(plan_layout(sorted(tmp_path.glob("*.png")), state[0], None)[0]) == 2
    state[0] = replace(state[0], media_width_mm=600, cutter_knife_mm=300)
    preview.refresh()
    wait_preview(preview)
    assert not preview.warning
    assert not preview.overflow
    preview.close()


def test_failed_image_read_keeps_previous_snapshot(tmp_path):
    app = QApplication.instance() or QApplication([])
    for i in range(2):
        Image.new("RGBA", (180, 250), "blue").save(tmp_path / f"{i}.png", dpi=(25.4, 25.4))
    preview = PairProductionPreview(lambda: LayoutSettings(cutter_mode="dual"))
    preview.use_folder(str(tmp_path))
    wait_preview(preview)
    previous = preview.planned
    (tmp_path / "1.png").unlink()
    (tmp_path / "0.png").unlink()
    preview.refresh()
    wait_preview(preview)
    assert preview.planned == previous
    assert "保留上次预览" in preview.warning
    preview.close()


def test_detail_preview_finds_actual_sides_across_export_prefixes(tmp_path):
    app = QApplication.instance() or QApplication([])
    first = tmp_path/'CVC面料00001-BORDER-1-T-White-L-NO1-1.png'
    other = tmp_path/'CVC面料00002-BOTHER-1-T-White-L-NO1-1.png'
    second = tmp_path/'CVC面料00003-BORDER-1-T-White-L-NO1-2.png'
    for path in (first, other, second):
        Image.new('RGBA', (100, 180), 'blue').save(path, dpi=(25.4,25.4))
    preview = PairProductionPreview(lambda: LayoutSettings(dpi=25.4,
        cutter_mode='dual', cutter_auto_knife=True, number_images=False))
    preview.use_folder(str(tmp_path))
    wait_preview(preview)
    assert [p for p, _ in preview.planned] == [first, second]
    assert preview.planned[0][1].y_px == preview.planned[1][1].y_px
    preview.set_overview(True)
    assert len(preview.planned) == 3
    preview.set_overview(False)
    assert [p for p, _ in preview.planned] == [first, second]
    preview.close()
