"""Cache retention is absolute and only expires disposable geometry records."""
from automatic_print.layout_engine.planning.cache import plan_cache


def test_cache_expires_at_24_hours_and_hits_do_not_extend_it(monkeypatch):
    now = [100000.0]
    monkeypatch.setattr(plan_cache, 'time', lambda: now[0])
    result = ([], {}, 100, 200, 200)
    plan_cache.save('old', result, {}, 50)
    now[0] += plan_cache.TTL_SECONDS-1
    assert plan_cache.load('old')[0] == result
    plan_cache.save('fresh', result, {}, 50)
    now[0] += 1
    assert plan_cache.load('old') is None
    assert plan_cache.load('fresh') is not None
    with plan_cache.connect() as db:
        assert db.execute('SELECT key FROM plans').fetchall() == [('fresh',)]


def test_next_access_cleans_all_expired_entries_but_not_other_files(tmp_path, monkeypatch):
    now = [100000.0]
    monkeypatch.setattr(plan_cache, 'time', lambda: now[0])
    source = tmp_path/'source.png'
    source.write_bytes(b'source must remain')
    history = plan_cache.cache_directory()/'history.json'
    plan_cache.save('a', ([], {}, 100, 200, 200), {}, 50)
    history.write_text('history must remain')
    plan_cache.save('b', ([], {}, 100, 200, 200), {}, 50)
    now[0] += plan_cache.TTL_SECONDS+1
    assert plan_cache.load('missing') is None
    with plan_cache.connect() as db:
        assert db.execute('SELECT count(*) FROM plans').fetchone()[0] == 0
    assert source.read_bytes() == b'source must remain'
    assert history.read_text() == 'history must remain'


def test_cache_lock_wait_is_bounded():
    with plan_cache.connect() as db:
        timeout = db.execute('PRAGMA busy_timeout').fetchone()[0]
    assert timeout <= 250
