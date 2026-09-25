import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import json
from io import BytesIO

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from automatic_print import __release_notes__, __version__, __version_display__
from automatic_print.automation.api.machine_status import identity
from automatic_print.updates.versioning import release_display
from automatic_print.updates import release as updater
from automatic_print.updates.source import SourceUpdateInfo
from automatic_print.ui.main_window import MainWindow

APP = QApplication.instance() or QApplication([])
OWNERS = []


def test_version_is_date_and_fixed_daily_iteration(tmp_path):
    assert __version_display__ == '0.1.404 · 2026-09-25 · 第07次更新'
    prefs = QSettings(str(tmp_path/'version.ini'), QSettings.IniFormat)
    for _ in range(2):
        window = MainWindow(prefs)
        OWNERS.append(window)
        window.startup_update_timer.stop()
        assert window.version_label.text() == '版本 '+__version_display__
        assert __version__ in window.version_label.text()
        assert __version__ in window.version_label.toolTip()
        window.close()
    assert release_display('0.1.1', '2026-09-14', 1) == '0.1.1 · 2026-09-14 · 第01次更新'
    assert any('打印历史' in item for item in __release_notes__)


def test_loading_isolated_preferences_does_not_replace_machine_identity(
    tmp_path, monkeypatch,
):
    machine_name = tmp_path / 'machine-name'
    machine_name.write_text('M11', encoding='utf-8')
    monkeypatch.setattr(identity, 'machine_name_file', lambda: machine_name)
    prefs = QSettings(str(tmp_path / 'isolated.ini'), QSettings.IniFormat)
    prefs.setValue('layout/machine_number', 'M1')

    window = MainWindow(prefs)
    OWNERS.append(window)
    window.startup_update_timer.stop()
    assert window.label_settings.machine.currentData() == 'M1'
    assert machine_name.read_text(encoding='utf-8') == 'M11'
    window.close()


def test_historical_source_metadata_does_not_invent_iteration():
    info = SourceUpdateInfo('a', 'b', '0.1.1', '2026-09-12', 1)
    assert info.display_version == '0.1.1 · 2026-09-12 · 历史版本'


def test_release_notes_carry_date_and_daily_count(monkeypatch):
    data = {'tag_name': 'v0.1.81', 'published_at': '2026-09-14T01:00:00Z',
            'html_url': 'https://example.test/release',
            'body': '发版日期：2026-09-13\n当日更新次数：20'}
    monkeypatch.setattr(updater, 'urlopen', lambda *a, **kw: BytesIO(json.dumps(data).encode()))
    info = updater.fetch_latest_release()
    assert info.version == '0.1.81'
    assert info.display_version == '0.1.81 · 2026-09-13 · 第20次更新'
