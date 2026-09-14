import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
from time import monotonic
from threading import get_ident, Event
from PIL import Image
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtTest import QTest
from automatic_print.layout import LayoutSettings
from automatic_print.cancellation import Cancellation
from automatic_print.history.bulk_analysis import analyze_folders, summary_text
from automatic_print.history.store import load_runs
from automatic_print.ui.bulk_film_analysis import BulkFilmAnalysisDialog

APP = QApplication.instance() or QApplication([])
OWNERS = []


def folders(tmp_path):
    result = []
    for batch in ('first', 'second'):
        path = tmp_path/batch
        path.mkdir()
        for side in (1, 2):
            Image.new('RGBA', (200, 300), 'blue').save(
                path/f'B1-1-T-Black-M-NO1-{side}.png', dpi=(25.4, 25.4))
        result.append(path)
    return result


def settings():
    return LayoutSettings(dpi=25.4, media_width_mm=580, number_images=False)


def test_many_folders_remain_independent_and_logs_share_group(tmp_path):
    inputs = folders(tmp_path)
    empty = tmp_path/'empty'
    empty.mkdir()
    path = tmp_path/'history.sqlite3'
    result = analyze_folders([inputs[0], empty, inputs[1], inputs[0]], settings(), path=path)
    assert len(result['records']) == 2 and len(result['errors']) == 1
    records = load_runs(path)
    assert len(records) == 2
    assert {r['group_id'] for r in records} == {result['group_id']}
    assert all(r['status'] == '仅分析' and r['image_count'] == 2 for r in records)
    assert all(len(r['comparison']['rows']) == 18 for r in records)
    assert len(list(tmp_path.rglob('*.png'))) == 4  # No composite output.
    assert '汇总 2 个完成批次' in summary_text(records)
    from automatic_print.ui.film_history import FilmHistoryPage
    page = FilmHistoryPage(path=path)
    OWNERS.append(page)
    page.refresh()
    page.summarize()
    assert '汇总 2 个完成批次' in page.details.toPlainText()


def test_stop_keeps_completed_batch_and_does_not_read_next(tmp_path):
    inputs = folders(tmp_path)
    cancel = Cancellation()
    def progress(index, folder, stage, *_):
        if stage == '批次分析完成':
            cancel.request()
    result = analyze_folders(inputs, settings(), progress, cancel, tmp_path/'history.sqlite3')
    assert result['stopped'] and len(result['records']) == 1
    assert len(load_runs(tmp_path/'history.sqlite3')) == 1


def test_summary_does_not_rank_partial_coverage_as_best():
    good = {'film_mm': 600, 'rotation_allowed': False, 'error': '',
            'film_area_m2': 2, 'length_m': 3, 'image_area_m2': 1}
    partial = dict(good, film_mm=400, film_area_m2=.1)
    records = [{'comparison': {'rows': [good, partial]}},
               {'comparison': {'rows': [good, dict(partial, error='no fit')]}}]
    text = summary_text(records)
    assert '理论面积最省：60厘米' in text
    assert '部分批次无解，不参与排名' in text


def test_dialog_runs_off_gui_and_releases_thread(tmp_path, monkeypatch):
    import automatic_print.ui.bulk_film_analysis as module
    app = QApplication.instance() or QApplication([])
    class Parent(QWidget):
        def _layout_settings(self):
            return settings()
    parent = Parent()
    dialog = BulkFilmAnalysisDialog(parent)
    OWNERS.extend((parent, dialog))
    inputs = folders(tmp_path)
    dialog.add_folders(inputs+inputs)
    assert dialog.folders.count() == 2
    caller, observed = get_ident(), []
    def analyze(*args):
        observed.append(get_ident())
        return {'records': [], 'errors': [], 'stopped': False, 'seconds': .1}
    monkeypatch.setattr(module, 'analyze_folders', analyze)
    dialog.show()
    dialog.begin()
    assert not dialog.start.isEnabled()
    deadline = monotonic()+5
    while dialog.thread:
        assert monotonic() < deadline
        app.processEvents()
        QTest.qWait(10)
    assert observed and observed[0] != caller
    assert dialog.start.isEnabled() and '已完成' in dialog.status.text()
    assert dialog.grab().save(str(tmp_path/'bulk-dialog.png'))
    dialog.close()
    parent.close()


def test_close_requests_stop_without_deleting_running_thread(tmp_path, monkeypatch):
    import automatic_print.ui.bulk_film_analysis as module
    class Parent(QWidget):
        def _layout_settings(self):
            return settings()
    parent = Parent()
    dialog = BulkFilmAnalysisDialog(parent)
    OWNERS.extend((parent, dialog))
    dialog.add_folders(folders(tmp_path))
    entered, release = Event(), Event()
    def analyze(*args):
        entered.set()
        release.wait(5)
        return {'records': [], 'errors': [], 'stopped': True, 'seconds': .1}
    monkeypatch.setattr(module, 'analyze_folders', analyze)
    dialog.show()
    dialog.begin()
    deadline = monotonic()+5
    try:
        while not entered.is_set():
            assert monotonic() < deadline
            APP.processEvents()
            QTest.qWait(10)
        thread = dialog.thread
        dialog.close()
        assert dialog.isVisible() and dialog.thread is thread
        assert thread.isRunning()
    finally:
        release.set()
        while dialog.thread and monotonic() < deadline:
            APP.processEvents()
            QTest.qWait(10)
    assert dialog.thread is None and '已停止' in dialog.status.text()
    dialog.close()
    parent.close()
