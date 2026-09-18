import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from threading import Barrier

from PIL import Image
import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from automatic_print.layout_engine import LayoutSettings, generate_layout
from automatic_print.layout_engine.pipeline import service
from automatic_print.layout_engine.rendering.storage.segmented_output import use_process_pool
from automatic_print.layout_engine.cutting.validation.cut_validation import corridor_checks
from automatic_print.ui.settings.output import SegmentedOutputSettings

APP = QApplication.instance() or QApplication([])


def test_parallel_choices_default_and_persist(tmp_path):
    prefs = QSettings(str(tmp_path/'parallel.ini'), QSettings.IniFormat)
    panel = SegmentedOutputSettings(prefs)
    assert panel.workers.value() == 4
    assert (panel.workers.minimum(), panel.workers.maximum()) == (1, 8)
    panel.parts.setValue(8)
    panel.workers.setValue(8)
    prefs.sync()
    reopened = SegmentedOutputSettings(prefs)
    assert reopened.parts.value() == 8
    assert reopened.workers.value() == 8


@pytest.mark.parametrize('parallel', [4, 8])
@pytest.mark.parametrize('engine', ['pillow', 'libvips'])
def test_selected_parallelism_really_runs_more_than_two_safe_segments(tmp_path, monkeypatch, parallel, engine):
    paths = []
    for i in range(16):
        path = tmp_path/f'B{i:02d}-1-T-Black-M-NO1-1.png'
        Image.new('RGBA', (80, 120), 'blue').save(path, dpi=(25.4, 25.4))
        paths.append(path)
    settings = LayoutSettings(
        dpi=25.4, cutter_mode='dual', number_images=False, output_parts=8,
        save_parallelism=parallel, save_memory_unlimited=True, png_engine=engine)
    process_parallel = use_process_pool(settings, parallel)
    barrier = Barrier(parallel)
    original = service.generate_layout

    def synchronized_render(*args, **kwargs):
        if kwargs.get('prepared_plan') is not None and not process_parallel:
            barrier.wait(timeout=30)  # Full-suite image I/O can delay Windows thread startup.
        return original(*args, **kwargs)

    monkeypatch.setattr(service, 'generate_layout', synchronized_render)
    result = generate_layout(paths, tmp_path/'out', settings)
    assert result['segment_count'] == 8
    assert result['actual_save_parallelism'] == parallel
    assert result['save_execution'] == (
        '独立进程并行' if process_parallel else '线程并行'
    )
    assert len(set(result['files'])) == 8
    assert len(result['placements']) == len(paths)
    for part in result['parts']:
        assert part['cut_corridor']['pixel_verified']
        with Image.open(tmp_path/'out'/part['filename']) as output:
            for check in corridor_checks(part['cut_corridor']):
                stripe = output.crop((
                    check['safe_left_px'], check.get('start_y_px', 0),
                    check['safe_right_px'], check.get('end_y_px', output.height),
                ))
                assert stripe.getchannel('A').getextrema() == (0, 0)
