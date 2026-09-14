import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from dataclasses import replace
import numpy as np
import pytest
from PIL import Image
import pyvips
from automatic_print.layout import LayoutSettings
from automatic_print.layout_engine.atomic_png import save_png
from automatic_print.layout_engine.png_codecs import fast


@pytest.mark.parametrize('vips', [False, True])
@pytest.mark.parametrize('level', [0, 1, 3])
def test_native_png_preserves_every_channel_dpi_and_long_dimensions(tmp_path, vips, level):
    pixels = np.random.default_rng(17).integers(0, 256, (2500, 512, 4), dtype=np.uint8)
    # More than 4MiB compressed exercises multiple IDAT chunks and their CRCs.
    canvas = (pyvips.Image.new_from_memory(pixels.tobytes(), 512, 2500, 4, 'uchar')
              if vips else Image.fromarray(pixels))
    settings = LayoutSettings(png_fast_encoding=True, save_memory_unlimited=True,
                              dpi=300, png_compression_level=level)
    target = tmp_path/'中文批次.png'
    reports = []
    details = save_png(canvas, target, settings, vips, lambda *a: reports.append(a))
    assert '原生快速PNG' in details['encoder']
    assert len(details['steps']) == 3
    assert not target.with_name(target.name+'.未完成').exists()
    with Image.open(target) as decoded:
        assert decoded.mode == 'RGBA'
        assert decoded.size == (512, 2500)
        assert decoded.info['dpi'] == pytest.approx((300,300), abs=.01)
        assert np.array_equal(np.asarray(decoded), pixels)
    with Image.open(target) as decoded:
        decoded.verify()
    native = pyvips.Image.new_from_file(str(target))
    assert native.xres*25.4 == pytest.approx(300, abs=.01)
    assert bytes(native.write_to_memory()) == pixels.tobytes()
    assert reports[-1][1] > 0


@pytest.mark.parametrize('reason', ['dependency', 'failure', 'budget'])
def test_fast_encoder_falls_back_without_losing_pixels(tmp_path, monkeypatch, reason):
    settings = LayoutSettings(png_fast_encoding=True, save_memory_unlimited=True)
    if reason == 'dependency':
        monkeypatch.setattr(fast, 'deflate_encode', None)
    elif reason == 'failure':
        def failed(*a): raise RuntimeError('test failure')
        monkeypatch.setattr(fast, 'encode_pixels', failed)
    else:
        settings = replace(settings, save_memory_unlimited=False, save_memory_mb=0)
    pixels = np.random.default_rng(2).integers(0, 256, (60, 50, 4), dtype=np.uint8)
    target = tmp_path/'fallback.png'
    details = save_png(Image.fromarray(pixels), target, settings, False, None)
    assert details['encoder'] == '标准兼容PNG'
    assert details['fallback_reason']
    with Image.open(target) as image:
        assert np.array_equal(np.asarray(image), pixels)


def test_gui_fast_save_defaults_and_persists(tmp_path):
    from test_developer_mode import window
    owner = window(tmp_path/'prefs.ini')
    assert owner.segmented_output.fast_png.isChecked()
    assert owner._layout_settings().png_streaming
    assert not owner._layout_settings().png_fast_encoding
    owner.segmented_output.fast_png.setChecked(False)
    assert not owner._layout_settings().png_streaming
    owner.close()
    fresh = window(tmp_path/'prefs.ini')
    assert not fresh.segmented_output.fast_png.isChecked()
    panel = fresh.automation_home.label_quick_panel
    panel.summary.save_report = '保存编码器：原生快速PNG\nPNG文件写入：0.100 秒'
    panel.timings.copy_report()
    from PySide6.QtWidgets import QApplication
    assert 'PNG文件写入：0.100 秒' in QApplication.clipboard().text()
    panel.summary.start('next-batch')
    assert panel.summary.save_report == ''
    fresh.close()


def test_progress_cancellation_is_not_swallowed_by_codec_fallback(tmp_path):
    from automatic_print.cancellation import TaskCancelled
    def cancelled(*a): raise TaskCancelled('test cancellation')
    target = tmp_path/'cancelled.png'
    with pytest.raises(TaskCancelled):
        save_png(Image.new('RGBA', (50,60)), target,
            LayoutSettings(png_fast_encoding=True, save_memory_unlimited=True), False, cancelled)
    assert not target.exists()
