"""Preserved production failures from the 2026-09-19 cold ten-batch run.

Set RUN_DTF_REAL_REGRESSION=1 only for an explicitly requested real-batch run.
The default test verifies the immutable case inventory without scanning DTF.
"""

import json
import os
from dataclasses import replace
from pathlib import Path

import pytest

from automatic_print.layout_engine import LayoutSettings, discover_images


CASES_FILE = Path(os.getenv(
    'DTF_FAILURE_CASES_FILE',
    Path(__file__).parent / 'fixtures' / 'dtf_failed_batches_20260919.json',
))
CASES = json.loads(CASES_FILE.read_text(encoding='utf-8')) if CASES_FILE.is_file() else None


def test_all_four_failed_batches_and_exact_settings_are_preserved():
    if CASES is None:
        pytest.skip('本机私有原图案例清单未提供')
    assert isinstance(CASES['seed'], int) and CASES['seed'] > 0
    assert len({Path(case['folder']).name for case in CASES['cases']}) == 4
    assert all(case['image_count'] > 0 and case['source_files'] for case in CASES['cases'])
    assert all(case['failed_stage'] == '刀位与排版计算' for case in CASES['cases'])
    assert all(case['diagnostic'] == '标签文字未位于刀码与膜标签之间的安全空白'
               for case in CASES['cases'])
    assert CASES['settings']['membrane_gap_mm'] == 41.0
    assert CASES['settings']['cutter_left_marker_external'] is True
    assert CASES['settings']['platform_reuse_qr'] is True
    assert CASES['settings']['worker_threads'] == 8


@pytest.mark.skipif(os.getenv('RUN_DTF_REAL_REGRESSION') != '1',
                    reason='真实批次完整生成需用户明确授权；默认不运行')
@pytest.mark.parametrize('case', CASES['cases'] if CASES else [],
                         ids=lambda case: Path(case['folder']).name)
def test_failed_batch_can_generate_safely_with_original_images(case, tmp_path, monkeypatch):
    """Require real production output without bypassing any safety checks."""
    from PySide6.QtCore import Qt
    from automatic_print.ui.workers import GenerateWorker

    folder = Path(case['folder'])
    if not folder.is_dir():
        pytest.skip(f'DTF 原图目录不可访问：{folder}')
    paths = discover_images(folder)
    assert len(paths) == case['image_count']
    assert all((folder / name).is_file() for name in case['source_files'])
    cache = tmp_path / 'cold-cache'
    cache.mkdir()
    monkeypatch.setenv('LOCALAPPDATA', str(cache))
    values = dict(CASES['settings'])
    for name in ('force_small_pair_sizes', 'dimension_overrides', 'header_gap_overrides',
                 'width_adjustments', 'manual_rotations', 'sequence_numbers'):
        if name in values:
            values[name] = tuple(values[name])
    settings = replace(LayoutSettings(**values), platform_name='Haloo')
    output = tmp_path / 'output'
    worker = GenerateWorker(paths, folder, output, 'DTF_REGRESSION', settings,
                            batch_name=folder.name)
    worker._save_history = lambda _result: None
    completed, failures = [], []
    worker.finished.connect(lambda path, result: completed.append((path, result)),
                            Qt.ConnectionType.DirectConnection)
    worker.failed.connect(failures.append, Qt.ConnectionType.DirectConnection)
    worker.run()
    if failures:
        assert not list(output.rglob('*.png')), '失败批次不能发布可打印PNG'
        pytest.fail(f"{folder.name} 在{case['failed_stage']}仍失败：{failures[0]}")
    assert len(completed) == 1
    assert completed[0][1]['files'], '必须生成真实输出文件'
