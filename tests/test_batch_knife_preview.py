import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from dataclasses import replace
from PIL import Image
import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from automatic_print.layout import LayoutSettings, generate_layout
from automatic_print.layout_engine.planner import plan_layout
from automatic_print.ui.main_window import MainWindow


def _sources(tmp_path):
    paths = []
    for i, width in enumerate((100, 350, 100, 350)):
        path = tmp_path / f"{i}.png"
        Image.new("RGBA", (width, 300), "blue").save(path, dpi=(25.4, 25.4))
        paths.append(path)
    return paths


def _settings():
    return LayoutSettings(media_width_mm=600, dpi=25.4, margin_mm=0,
                          cutter_mode="dual", cutter_auto_knife=True,
                          number_images=False)


def test_whole_batch_knife_is_asymmetric_fixed_and_recorded(tmp_path):
    paths = _sources(tmp_path)
    payloads = []
    result = generate_layout(paths, tmp_path / "out", _settings(), plan_ready=payloads.append)
    knife = round(result["cutter_knife_mm"], 6)
    assert knife != 300
    assert result["height_px"] == 600 + _settings().spacing_mm
    assert payloads[0]["settings"].cutter_knife_mm == pytest.approx(knife)
    right_markers = [p["color_block_x_px"] for p in result["placements"] if p["x_px"] > knife]
    assert len(right_markers) == 2
    assert len(set(right_markers)) == 1
    assert right_markers[0] == pytest.approx(result["right_marker_mm"])
    for p in result["placements"]:
        if p["x_px"] < knife:
            assert p["x_px"] + p["width_px"] <= knife-3
        else:
            assert p["x_px"] >= knife+3
            assert p["x_px"] + p["width_px"] <= 600
    with pytest.raises(ValueError):
        plan_layout(paths, replace(_settings(), cutter_auto_knife=False), None)


def test_generation_preview_uses_worker_positions_and_keeps_saving_frame(tmp_path):
    app = QApplication.instance() or QApplication([])
    paths = _sources(tmp_path)
    payloads = []
    generate_layout(paths, tmp_path / "out", _settings(), plan_ready=payloads.append)
    prefs = QSettings(str(tmp_path / "ui.ini"), QSettings.Format.IniFormat)
    window = MainWindow(preferences=prefs)
    controller, bridge = window.generation_preview, window.worker_bridge
    controller.start()
    bridge.layout_preview.emit(payloads[0])
    preview = controller.preview
    assert len(preview.planned) == 4
    assert preview.render_settings.cutter_knife_mm == payloads[0]["settings"].cutter_knife_mm
    bridge.layout_progress.emit("合成图片", 4, 4, paths[-1].name)
    frame = preview.planned
    bridge.layout_progress.emit("保存图片", 0, 1000000, "print.png")
    assert preview.planned == frame
    assert "保存图片" in preview.production_stage
    controller.end()
    assert preview.planned == frame
    assert not preview.production_active
    # A second task must not keep any previous plan, errors or thumbnails.
    preview.warning = "旧批次错误"
    preview.images[paths[0]] = object()
    preview.schedule_refresh()
    controller.start()
    assert not preview.planned
    assert preview.item is None
    assert preview.batch_payload is None
    assert preview.render_settings is None
    assert not preview.images
    assert not preview.warning
    assert not preview.refresh_timer.isActive()
    assert "新" in preview.detail
    # Reusing the same settings object must still install the new task data.
    bridge.layout_preview.emit(payloads[0])
    assert len(preview.planned) == 4
    assert preview.batch_payload is payloads[0]
    controller.end()
    window.close()
