from types import SimpleNamespace
from test_developer_mode import window


def test_close_keeps_active_task_running(tmp_path):
    owner = window(tmp_path/'prefs.ini')
    owner.thread = object()
    owner.worker = SimpleNamespace(request_cancel=lambda: None)
    owner.close()
    assert owner.isVisible()
    assert '任务仍在运行' in owner.status.text()
    owner.thread = owner.worker = None
    owner.close()
    assert not owner.isVisible()


def test_pause_routes_to_active_multi_batch_without_exiting(tmp_path):
    owner=window(tmp_path/'prefs.ini')
    cancelled=[]
    owner.bulk_controller=SimpleNamespace(thread=object(),cancel=lambda:cancelled.append(True))
    owner.stop_generation_button.setEnabled(True)
    owner.stop_generation()
    assert cancelled==[True]
    owner.bulk_controller.thread=None
    owner.close()


def test_development_restart_never_force_kills_running_task():
    source = (__import__('pathlib').Path(__file__).parents[1]/'dev.py').read_text(
        encoding='utf-8'
    )
    assert 'process.kill()' not in source
    assert 'process.wait(timeout=' not in source


def test_failed_encoding_keeps_pending_file_and_does_not_overwrite_it(tmp_path):
    from automatic_print.layout_engine.rendering.storage.atomic_png import save_png
    from automatic_print.layout_engine.output.output_name import unused_output_path
    import pytest
    target = tmp_path/'batch.png'
    class Canvas:
        def save(self, path, **kwargs):
            path.write_bytes(b'partial')
            raise OSError('failed encoder')
        def close(self): pass
    with pytest.raises(OSError, match='failed encoder'):
        save_png(Canvas(), target, SimpleNamespace(dpi=300, png_compression_level=1), False, None)
    assert not target.exists()
    assert target.with_name('batch.png.未完成').read_bytes() == b'partial'
    assert unused_output_path(tmp_path, 'batch.png').name == 'batch (2).png'
