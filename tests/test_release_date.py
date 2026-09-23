from datetime import date
from io import BytesIO
import json
from pathlib import Path

from automatic_print import __version__, __release_date__, __version_display__
from automatic_print.updates import release as updater


def test_local_release_date_is_fixed_and_separate_from_version():
    assert date.fromisoformat(__release_date__)
    assert __release_date__ in __version_display__
    assert __version__ in __version_display__
    assert '次更新' in __version_display__
    assert updater.version_tuple(__version__) == tuple(map(int, __version__.split('.')))


def test_test_computer_bootstrap_uses_current_source_version():
    readme = (Path(__file__).parents[1] / 'README.md').read_text(encoding='utf-8')
    assert f'bootstrap-test-computer.ps1?v={__version__}' in readme


def test_remote_release_uses_publication_date(monkeypatch):
    data = {'tag_name': 'v0.1.999', 'html_url': 'https://example.com/release',
            'published_at': '2026-09-14T08:30:00Z'}
    monkeypatch.setattr(updater, 'urlopen',
                        lambda *args, **kwargs: BytesIO(json.dumps(data).encode()))
    update = updater.fetch_latest_release()
    assert update.release_date == '2026-09-14'
    assert update.display_version == '0.1.999 · 2026-09-14 · 历史版本'
    assert update.version == '0.1.999'
    assert updater.version_tuple(update.version) > updater.version_tuple(__version__)


def test_missing_remote_date_is_not_replaced_with_today():
    update = updater.UpdateInfo('0.1.61', '', '', '')
    assert update.display_version == '0.1.61 · 日期未知 · 历史版本'
