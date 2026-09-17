import os
import subprocess
import sys
from types import SimpleNamespace
from time import monotonic
from test_developer_mode import window


def test_pause_cancels_task_but_only_close_exits(tmp_path, intercept_process_exit):
    owner = window(tmp_path/'prefs.ini')
    cancelled=[]
    owner.thread = object()
    owner.worker = SimpleNamespace(request_cancel=lambda:cancelled.append(True))
    owner.stop_generation()
    assert cancelled==[True] and intercept_process_exit==[]
    assert owner.isVisible()
    assert '软件不会退出' in owner.status.text()
    owner.thread = owner.worker = None
    owner.close()
    assert intercept_process_exit == [0]
    assert not owner.isVisible()


def test_pause_routes_to_active_multi_batch_without_exiting(tmp_path,intercept_process_exit):
    owner=window(tmp_path/'prefs.ini')
    cancelled=[]
    owner.bulk_controller=SimpleNamespace(thread=object(),cancel=lambda:cancelled.append(True))
    owner.stop_generation_button.setEnabled(True)
    owner.stop_generation()
    assert cancelled==[True] and intercept_process_exit==[]
    owner.bulk_controller.thread=None
    owner.close()


def test_real_exit_interrupts_blocked_save_and_leaves_unfinished_markers(tmp_path):
    script = '''
import sys
from pathlib import Path
from threading import Thread, Event
from types import SimpleNamespace
from PySide6.QtCore import QCoreApplication
from automatic_print.ui import workers
from automatic_print.layout_engine.rendering.storage.atomic_png import save_png
from automatic_print.ui.immediate_exit import exit_now
app = QCoreApplication([])
root = Path(sys.argv[1])
entered = Event()
class Canvas:
    def save(self, path, **kwargs):
        Path(path).write_bytes(b'partial PNG')
        entered.set()
        Event().wait()
    def close(self): pass
def generate(images, output, settings, *args, **kwargs):
    save_png(Canvas(), output/'output.png', SimpleNamespace(dpi=300, png_compression_level=1), False, None)
workers.generate_layout = generate
worker = workers.GenerateWorker([], root, root/'task', 'job', None)
Thread(target=worker.run).start()
assert entered.wait(2)
noop = SimpleNamespace(stop=lambda: None)
prefs = SimpleNamespace(flush=lambda: (root/'saved-settings').touch())
fake = SimpleNamespace(startup_update_timer=noop, clock=noop, preference_autosave=prefs,
                       hide=lambda: None, settings_dialog=SimpleNamespace(hide=lambda: None))
exit_now(fake)
'''
    started = monotonic()
    result = subprocess.run([sys.executable, '-c', script, str(tmp_path)],
                            env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'},
                            capture_output=True, timeout=5)
    assert result.returncode == 0, result.stderr.decode()
    assert monotonic()-started < 5
    assert (tmp_path/'saved-settings').exists()
    assert (tmp_path/'task'/'批次未完成，禁止打印.txt').exists()
    assert (tmp_path/'task'/'output.png.未完成').exists()
    assert not (tmp_path/'task'/'output.png').exists()


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
