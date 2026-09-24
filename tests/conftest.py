"""UI tests intercept explicit process exit; subprocess tests exercise real exit."""
import pytest


@pytest.fixture(autouse=True)
def isolated_plan_cache(tmp_path, monkeypatch):
    from automatic_print.layout_engine.measurement import measurement_cache
    from automatic_print.layout_engine.planning.cache import plan_cache
    monkeypatch.setattr(plan_cache, 'cache_directory', lambda: tmp_path/'plan-cache')
    monkeypatch.setattr(measurement_cache, 'cache_directory', lambda: tmp_path/'measurement-cache')
    monkeypatch.setenv(
        'AUTOMATIC_PRINT_COMMAND_JOURNAL', str(tmp_path/'command-journal.sqlite3'),
    )
