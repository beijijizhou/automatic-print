import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import json
from io import BytesIO

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from automatic_print import __version__, __version_display__
from automatic_print.versioning import release_display
from automatic_print import updater
from automatic_print.updates.source import SourceUpdateInfo
from automatic_print.ui.main_window import MainWindow

APP = QApplication.instance() or QApplication([])
OWNERS = []


def test_version_is_date_and_fixed_daily_iteration(tmp_path):
    assert __version_display__ == '2026-09-13 · 第24次更新'
    prefs = QSettings(str(tmp_path/'version.ini'), QSettings.IniFormat)
    for _ in range(2):
        window = MainWindow(prefs)
        OWNERS.append(window)
        window.startup_update_timer.stop()
        assert window.version_label.text() == '版本 '+__version_display__
        assert __version__ not in window.version_label.text()
        assert __version__ in window.version_label.toolTip()
        window.close()
    assert release_display('2026-09-14', 1) == '2026-09-14 · 第01次更新'


def test_historical_source_metadata_does_not_invent_iteration():
    info = SourceUpdateInfo('a', 'b', '0.1.1', '2026-09-12', 1)
    assert info.display_version == '2026-09-12 · 历史版本'


def test_release_notes_carry_date_and_daily_count(monkeypatch):
    data = {'tag_name': 'v0.1.81', 'published_at': '2026-09-14T01:00:00Z',
            'html_url': 'https://example.test/release',
            'body': '发版日期：2026-09-13\n当日更新次数：20'}
    monkeypatch.setattr(updater, 'urlopen', lambda *a, **kw: BytesIO(json.dumps(data).encode()))
    info = updater.fetch_latest_release()
    assert info.version == '0.1.81'
    assert info.display_version == '2026-09-13 · 第20次更新'
