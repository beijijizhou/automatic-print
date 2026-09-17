from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
import json
from hashlib import sha256

import numpy as np
from PIL import Image
import pytest

from automatic_print.layout_engine import generate_layout
from automatic_print.layout_engine.planning.base import planner
from automatic_print.layout_engine.planning.cache import plan_cache
from automatic_print.layout_engine.measurement.measurement_session import measurement_session
from test_parallel_film_geometry import qr_sources, settings


def config(**updates):
    return replace(settings(), compare_film_sizes=True, compare_reference_films=False, **updates)


def test_second_plan_from_disk_skips_measurement_and_all_geometry(tmp_path, monkeypatch):
    paths = qr_sources(tmp_path)
    reports = []
    first = planner.plan_layout(paths, config(), None, reports.append)
    monkeypatch.setattr(planner, '_measured_plan', lambda *a: pytest.fail('Recomputed cached batch'))
    monkeypatch.setattr(Image, 'open', lambda *a, **kw: pytest.fail('Opened source pixels during cached planning'))
    progress, cached = [], []
    second = planner.plan_layout(paths, config(worker_threads=1, output_parts=3),
                                 lambda *a: progress.append(a), cached.append)
    assert second == first
    assert cached[0]['cache']['hit']
    assert cached[0]['film_comparison']['seconds'] == 0
    assert any('缓存命中' in p[3] for p in progress)
    assert (plan_cache.cache_directory()/'排版缓存.sqlite3').is_file()


def test_file_parameters_date_and_version_invalidate_cache_key(tmp_path, monkeypatch):
    path = tmp_path/'B1-1-T-Black-M-NO1-1.png'
    path.write_bytes(b'original')
    now = datetime(2026, 9, 14)
    def key(s=config(), date=now):
        with measurement_session():
            return plan_cache.cache_key([path], s, date)
    original = key()
    assert key(config(media_width_mm=430)) != original
    assert key(config(platform_name='测试平台')) != original
    assert key(config(machine_number='M2')) != original
    assert key(config(worker_threads=1, output_parts=8)) == original
    dated = config(label_text_template='{日期}')
    assert key(dated, now) != key(dated, now+timedelta(days=1))
    path.write_bytes(b'changed source')
    assert key() != original
    import automatic_print
    before = key()
    monkeypatch.setattr(automatic_print, '__version__', 'next-algorithm')
    assert key() != before


def test_corrupt_and_geometrically_invalid_cache_recompute_instead_of_blocking(tmp_path, monkeypatch):
    paths = qr_sources(tmp_path)
    first = planner.plan_layout(paths, config(), None)
    with plan_cache.connect() as db:
        db.execute("UPDATE plans SET digest='corrupted'")
    original, calls = planner._measured_plan, []
    def counted(*a):
        calls.append(1)
        return original(*a)
    monkeypatch.setattr(planner, '_measured_plan', counted)
    assert planner.plan_layout(paths, config(), None) == first and len(calls) == 1
    with plan_cache.connect() as db:
        key, payload = db.execute('SELECT key, payload FROM plans').fetchone()
        data = json.loads(payload)
        data['placements'] = data['placements'][:-1]
        payload = json.dumps(data)
        db.execute('UPDATE plans SET payload=?, digest=? WHERE key=?',
                   (payload, sha256(payload.encode()).hexdigest(), key))
    assert planner.plan_layout(paths, config(), None) == first and len(calls) == 2


def test_cache_write_failure_is_nonfatal_and_source_change_during_hit_is_rejected(tmp_path, monkeypatch):
    paths = qr_sources(tmp_path)
    original = plan_cache.save
    def unavailable(*a):
        raise OSError('disk unavailable')
    monkeypatch.setattr(plan_cache, 'save', unavailable)
    progress = []
    planner.plan_layout(paths, config(), lambda *a: progress.append(a))
    assert any('不影响本次' in p[3] for p in progress)
    monkeypatch.setattr(plan_cache, 'save', original)
    planner.plan_layout(paths, config(), None)
    def changed(report):
        if report.get('cache', {}).get('hit'):
            paths[0].write_bytes(b'changed file')
    with pytest.raises(ValueError, match='发生变化'):
        planner.plan_layout(paths, config(), None, changed)


@pytest.mark.parametrize('engine', ['pillow', 'libvips'])
@pytest.mark.parametrize('parts', [1, 3])
def test_cached_production_still_verifies_whole_batch_and_real_source_pixels(tmp_path, monkeypatch, engine, parts):
    paths = qr_sources(tmp_path)
    planner.plan_layout(paths, config(), None)
    monkeypatch.setattr(planner, '_measured_plan', lambda *a: pytest.fail('Replanned cached batch'))
    result = generate_layout(paths, tmp_path/'out', config(png_engine=engine, output_parts=parts,
                             save_memory_unlimited=True))
    assert result['analysis']['cache']['hit']
    for part in result.get('parts', [result]):
        assert part['order_check']
        for zone in part['cut_corridor'].get('zones', [part['cut_corridor']]):
            assert zone['pixel_verified']
        with Image.open(tmp_path/'out'/part['filename']) as output:
            for p in part['placements']:
                with Image.open(tmp_path/p['source']) as source:
                    original = np.asarray(source.rotate(p['rotation_degrees'], expand=True))
                actual = np.asarray(output.crop((p['x_px'], p['y_px'], p['x_px']+p['width_px'], p['y_px']+p['height_px'])))
                opaque = original[:, :, 3] == 255
                assert np.array_equal(actual[opaque], original[opaque])


def test_cache_survives_a_fresh_python_process(tmp_path):
    import subprocess
    import sys
    paths = qr_sources(tmp_path)
    planner.plan_layout(paths, config(), None)
    script = '''
import sys, json
from pathlib import Path
sys.path.insert(0, 'tests')
from test_persistent_plan_cache import config
from automatic_print.layout_engine.planning.base import planner
from automatic_print.layout_engine.planning.cache import plan_cache
plan_cache.cache_directory = lambda: Path(sys.argv[1])
def forbidden(*a):
    raise RuntimeError('process recomputed plan')
planner._measured_plan = forbidden
reports = []
result = planner.plan_layout([Path(p) for p in json.loads(sys.argv[2])], config(), None, reports.append)
assert reports[0]['cache']['hit'] and len(result[0]) == 12
'''
    child = subprocess.run([sys.executable, '-c', script, str(plan_cache.cache_directory()),
                            json.dumps([str(p) for p in paths])], capture_output=True, text=True, timeout=15)
    assert child.returncode == 0, child.stderr


def test_multiple_batches_can_share_the_local_database(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    batches = []
    for i in range(4):
        root = tmp_path/str(i)
        root.mkdir()
        batches.append(qr_sources(root))
    s = config(worker_threads=1)
    with ThreadPoolExecutor(4) as pool:
        results = list(pool.map(lambda paths: planner.plan_layout(paths, s, None), batches))
    assert all(len(r[0]) == 12 for r in results)
    with plan_cache.connect() as db:
        assert db.execute('SELECT count(*) FROM plans').fetchone()[0] == 4
