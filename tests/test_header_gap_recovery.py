from pathlib import Path

import pytest

from automatic_print.layout_engine import LayoutSettings
from automatic_print.layout_engine.labeling.base import header_gap
from automatic_print.layout_engine.labeling.gap import cache_files
from test_header_gap import sample


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(header_gap, 'cache_root', lambda: tmp_path/'cache')


def test_windows_busy_cache_publish_retries_then_succeeds(tmp_path, monkeypatch):
    source = sample(tmp_path/'B1-1-T-Black-M-NO1-1.png')
    original_replace = Path.replace
    attempts = []

    def busy_twice(path, target):
        if path.name.endswith('.未完成') and Path(target).suffix == '.png':
            attempts.append(path)
            if len(attempts) <= 2:
                raise PermissionError(13, 'file is in use', str(path))
        return original_replace(path, target)

    monkeypatch.setattr(Path, 'replace', busy_twice)
    monkeypatch.setattr(cache_files, 'sleep', lambda _seconds: None)
    prepared, record = header_gap.prepare_one(
        source, LayoutSettings(dpi=25.4, membrane_gap_mm=40),
    )

    assert len(attempts) == 3
    assert prepared != source
    assert record['added_px'] == 32


def test_busy_cache_falls_back_to_original_and_keeps_batch_running(tmp_path, monkeypatch):
    source = sample(tmp_path/'B1-1-T-Black-M-NO1-1.png')
    original_replace = Path.replace

    def always_busy(path, target):
        if path.name.endswith('.未完成') and Path(target).suffix == '.png':
            raise PermissionError(13, 'file is in use', str(path))
        return original_replace(path, target)

    monkeypatch.setattr(Path, 'replace', always_busy)
    monkeypatch.setattr(cache_files, 'sleep', lambda _seconds: None)
    prepared, record = header_gap.prepare_one(
        source, LayoutSettings(dpi=25.4, membrane_gap_mm=40),
    )

    assert prepared == source
    assert record['added_px'] == 0
    assert '保留原图间距' in record['warning']
    assert '已继续排版' in record['warning']


def test_unexpected_single_image_gap_failure_keeps_other_images_running(tmp_path, monkeypatch):
    failed = sample(tmp_path/'FAILED-1-T-Black-M-NO1-1.png')
    healthy = sample(tmp_path/'HEALTHY-1-T-Black-M-NO1-1.png')
    original = header_gap.prepare_one

    def fail_one(path, settings):
        if Path(path) == failed:
            raise RuntimeError('pngsave: out of order read')
        return original(path, settings)

    monkeypatch.setattr(header_gap, 'prepare_one', fail_one)
    prepared, _, records = header_gap.prepare_paths(
        [failed, healthy], LayoutSettings(dpi=25.4, membrane_gap_mm=40),
    )

    assert prepared[0] == failed
    assert prepared[1] != healthy
    assert 'out of order read' in records[0]['warning']
    assert '已继续排版' in records[0]['warning']
    assert records[1]['added_px'] == 32


def test_optional_label_premeasure_failure_keeps_successful_gap(tmp_path):
    source = sample(tmp_path/'SMALL-1-T-Black-M-NO1-1.png')
    settings = LayoutSettings(
        dpi=25.4, membrane_gap_mm=40, platform_name='隆丰',
    )

    def fail_label_measurement(_index, _path, _settings):
        raise ValueError('小图平台文字没有安全空位')

    paths, adjusted, records = header_gap.prepare_paths(
        [source], settings, premeasure=fail_label_measurement,
    )

    assert paths == [source]
    assert records[0]['added_px'] == 32
    assert records[0]['warning'] == ''
    assert adjusted.header_gap_overrides
