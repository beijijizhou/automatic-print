"""Concurrent batches share the persistent plan database safely."""
from automatic_print.layout_engine.planning.base import planner
from automatic_print.layout_engine.planning.cache import plan_cache
from test_parallel_film_geometry import qr_sources
from test_persistent_plan_cache import config

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
