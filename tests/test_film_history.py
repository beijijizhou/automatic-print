import csv
import json
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import QApplication
from automatic_print.history.store import save_run, load_runs, export_csv
from automatic_print.layout import LayoutSettings
from automatic_print.layout_engine.film_comparison import compare_films
from automatic_print.ui.film_history import FilmHistoryPage
from automatic_print.ui.workers import GenerateWorker
from tests.test_film_comparison import sources


def record(tmp_path, path, job='job', preview=False):
    settings = LayoutSettings(dpi=25.4, media_width_mm=580, number_images=False, compare_reference_films=True)
    result = {'preview_only': preview, 'analysis': {'image_count': 6, 'order_count': 3,
              'film_comparison': compare_films(sources(tmp_path), settings)}}
    return save_run(job, tmp_path, tmp_path/'output', settings, result, path)


def test_durable_records_and_csv_include_all_numeric_alternatives(tmp_path):
    path = tmp_path/'logs'/'history.sqlite3'
    first = record(tmp_path, path)
    record(tmp_path, path, 'preview', True)
    runs = load_runs(path)
    assert len(runs) == 2
    assert len(runs[0]['comparison']['rows']) == 18
    assert runs[0]['status'] == '仅预览' and runs[0]['output_folder'] == ''
    assert runs[1] == json.loads(json.dumps(first))
    destination = tmp_path/'statistics.csv'
    export_csv(destination, runs)
    with destination.open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 36
    assert {float(row['方案膜宽毫米']) for row in rows} == set(range(400, 801, 50))
    assert all(float(row['实际膜宽毫米']) == 600 for row in rows)
    assert float(rows[0]['耗膜平方米']) > 0


def test_history_page_is_lazy_and_selection_never_opens_images(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    path = tmp_path/'history.sqlite3'
    page = FilmHistoryPage(path=path)
    assert not path.exists()
    record(tmp_path, path)
    from PIL import Image
    monkeypatch.setattr(Image, 'open', lambda *_a, **_k: (_ for _ in ()).throw(AssertionError('PNG read')))
    page.refresh()
    assert page.runs.rowCount() == 1 and page.comparison.rowCount() == 18
    assert '间隔5厘米' in page.details.toPlainText()
    page.resize(1100, 800)
    page.show()
    app.processEvents()
    assert page.grab().save(str(tmp_path/'history.png'))
    page.close()


def test_history_failures_do_not_block_finished_production(tmp_path, monkeypatch):
    import automatic_print.history.store as store
    import automatic_print.ui.workers as workers
    monkeypatch.setattr(store, 'save_run', lambda *_a, **_k: (_ for _ in ()).throw(OSError('disk unavailable')))
    monkeypatch.setattr(workers, 'generate_layout',
                        lambda *_a, **_k: {'analysis': {}, 'filename': tmp_path.name+'.png'})
    monkeypatch.setattr(workers, 'cutting_report', lambda *_a: 'report')
    worker = GenerateWorker([], tmp_path, tmp_path, 'job', LayoutSettings())
    finished, failed = [], []
    worker.finished.connect(lambda output, result: finished.append(result))
    worker.failed.connect(failed.append)
    worker.run()
    assert not failed and len(finished) == 1
    assert 'disk unavailable' in finished[0]['history_warning']
    assert (tmp_path/'manifest.json').exists()


def test_disabled_comparison_creates_no_history_database(tmp_path):
    path = tmp_path/'history.sqlite3'
    assert save_run('job', tmp_path, tmp_path, LayoutSettings(), {'analysis': {}}, path) is None
    assert not path.exists()


def test_successful_worker_appends_one_record_and_stopped_task_does_not(tmp_path, monkeypatch):
    import automatic_print.ui.workers as workers
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path/'appdata'))
    settings = LayoutSettings(dpi=25.4, media_width_mm=580, number_images=False)
    result = {'filename': tmp_path.name+'.png',
              'analysis': {'film_comparison': compare_films(sources(tmp_path), settings)}}
    monkeypatch.setattr(workers, 'generate_layout', lambda *_a, **_k: result)
    monkeypatch.setattr(workers, 'cutting_report', lambda *_a: 'report')
    worker = GenerateWorker([], tmp_path, tmp_path, 'completed', settings)
    worker.run()
    assert len(load_runs()) == 1
    stopped = GenerateWorker([], tmp_path, tmp_path, 'stopped', settings)
    stopped.request_cancel()
    stopped.run()
    assert len(load_runs()) == 1
