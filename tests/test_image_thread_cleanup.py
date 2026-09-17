from threading import get_ident, enumerate as threads
from dataclasses import replace
import pytest
from PIL import Image
from PySide6.QtCore import QObject, Slot, Qt
from automatic_print.layout_engine.intake.preparation import image_pipeline
from automatic_print.layout_engine.rendering.engines import pillow_renderer
from automatic_print.layout_engine.planning.film import film_comparison
from automatic_print.layout_engine.planning.rotation import rotation_compare
from automatic_print.layout_engine.rendering.storage.save_progress import monitor_save
from automatic_print.ui.workers import GenerateWorker
from test_parallel_film_geometry import qr_sources, settings


def forbidden(*args, **kwargs):
    raise AssertionError('Single-worker path created a nested pool')


def test_serial_image_preparation_stays_in_caller_thread_and_closes(tmp_path, monkeypatch):
    monkeypatch.setattr(image_pipeline, 'ThreadPoolExecutor', forbidden)
    caller, seen, images = get_ident(), [], []
    def prepare(item):
        seen.append(get_ident())
        image = Image.new('RGBA', (2, 2))
        images.append(image)
        return image, item
    stream = image_pipeline.prepared_images(prepare, range(10), 1)
    next(stream)
    stream.close()
    assert seen == [caller]
    with pytest.raises(ValueError):
        images[0].getpixel((0, 0))


def test_canvas_and_prepared_images_are_closed_on_progress_failure(tmp_path, monkeypatch):
    path = tmp_path/'source.png'
    Image.new('RGBA', (10, 20), 'blue').save(path)
    second = tmp_path/'second.png'
    Image.new('RGBA', (10, 20), 'green').save(second)
    opened = []
    original = pillow_renderer.Image.new
    def create(*args, **kwargs):
        image = original(*args, **kwargs)
        opened.append(image)
        return image
    monkeypatch.setattr(pillow_renderer.Image, 'new', create)
    # Obtain real validated placements instead of fabricating planner fields.
    from automatic_print.layout_engine import generate_layout, LayoutSettings
    payloads = []
    config = LayoutSettings(dpi=25.4, number_images=False, color_block_enabled=False, worker_threads=2)
    generate_layout([path, second], tmp_path/'unused', config, preview_only=True, plan_ready=payloads.append)
    planned = payloads[0]['planned']
    def fail(*args):
        raise RuntimeError('stop')
    with pytest.raises(RuntimeError, match='stop'):
        pillow_renderer.build_pillow_canvas(planned, {}, (600, 100), config, fail)
    with pytest.raises(ValueError):
        opened[0].getpixel((0, 0))
    assert not any(t.name.startswith('image-prepare') for t in threads())


def test_rotation_closes_original_decoded_image(monkeypatch):
    from types import SimpleNamespace
    original = Image.new('RGBA', (3, 2), 'blue')
    monkeypatch.setattr(pillow_renderer, 'normalized_image', lambda *_: original)
    placement = SimpleNamespace(rotation_degrees=90, width_px=2, height_px=3)
    image, _ = pillow_renderer._prepare(('unused.png', placement))
    assert image.size == (2, 3)
    with pytest.raises(ValueError):
        original.getpixel((0, 0))
    image.close()


def test_single_geometry_budget_does_not_spawn_comparison_pools(tmp_path, monkeypatch):
    paths = qr_sources(tmp_path)
    monkeypatch.setattr(film_comparison, 'ThreadPoolExecutor', forbidden)
    monkeypatch.setattr(rotation_compare, 'ThreadPoolExecutor', forbidden)
    config = replace(settings(), film_geometry_workers=1, compare_reference_films=False)
    result = film_comparison.compare_films(paths, config)
    assert len(result['rows']) == 4 and result['parallelism'] == 1
    from automatic_print.layout_engine.orders.batch_analysis import analyze_batch
    analysis = analyze_batch(paths, config)
    rotation_compare.compare_rotation(paths, config, None, analysis, None)
    assert analysis['rotation_comparison']['parallelism'] == 1


def test_save_reporter_is_joined_before_return(tmp_path):
    with monitor_save(tmp_path/'large.png', lambda *_: None):
        assert any(t.name == 'save-progress' for t in threads())
    assert not any(t.name == 'save-progress' for t in threads())


def test_large_byte_progress_survives_queued_qt_delivery(tmp_path):
    from test_developer_mode import APP, OWNERS
    received = []
    class Receiver(QObject):
        @Slot(str, object, object, str)
        def progress(self, stage, current, total, filename):
            received.append(current)
    receiver = Receiver()
    OWNERS.append(receiver)
    worker = GenerateWorker([], tmp_path, tmp_path/'out', 'test', settings())
    worker.progress.connect(receiver.progress, Qt.QueuedConnection)
    worker.progress.emit('保存图片', 5*1024**3, 0, 'large.png')
    APP.processEvents()
    assert received == [5*1024**3]
