"""UI tests intercept explicit process exit; subprocess tests exercise real exit."""
import pytest


@pytest.fixture(autouse=True)
def intercept_process_exit(monkeypatch):
    from automatic_print.ui import immediate_exit
    calls = []
    monkeypatch.setattr(immediate_exit, 'terminate_process', calls.append)
    return calls
