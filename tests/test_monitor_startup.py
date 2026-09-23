from pathlib import Path

from automatic_print.runtime.monitoring.startup import (
    RUN_VALUE,
    SCHEDULED_TASK,
    ensure_monitor_started,
    monitor_command,
)


def test_source_monitor_registration_uses_venv_pythonw(tmp_path):
    root = tmp_path / "AutomaticPrint"
    script = root / "run_printerexp_monitor.py"
    python = root / ".venv" / "Scripts" / "python.exe"
    pythonw = python.with_name("pythonw.exe")
    script.parent.mkdir(parents=True)
    python.parent.mkdir(parents=True)
    script.write_text("", encoding="utf-8")
    pythonw.write_text("", encoding="utf-8")
    registered, spawned = [], []
    stopped = []

    result = ensure_monitor_started(
        project_root=root,
        executable=python,
        frozen=False,
        platform_name="nt",
        stop_existing=lambda: stopped.append(True),
        start_scheduled=lambda: False,
        register=registered.append,
        spawn=lambda command, cwd: spawned.append((command, cwd)),
    )

    assert result is True
    assert stopped == [True]
    assert RUN_VALUE == "AutomaticPrintMonitor"
    assert str(pythonw) in registered[0]
    assert str(script) in registered[0]
    assert spawned == [([str(pythonw), str(script)], root)]


def test_existing_elevated_task_is_preferred_over_regular_startup(tmp_path):
    registered, spawned, removed = [], [], []

    result = ensure_monitor_started(
        project_root=tmp_path,
        executable=tmp_path / "python.exe",
        frozen=False,
        platform_name="nt",
        stop_existing=lambda: None,
        start_scheduled=lambda: True,
        unregister=lambda: removed.append(True),
        register=registered.append,
        spawn=lambda *args: spawned.append(args),
    )

    assert result is True
    assert SCHEDULED_TASK == "AutomaticPrintMonitor"
    assert removed == [True]
    assert registered == []
    assert spawned == []


def test_packaged_monitor_uses_sibling_executable(tmp_path):
    app = tmp_path / "AutomaticPrint.exe"
    monitor = tmp_path / "AutomaticPrintMonitor.exe"
    monitor.write_text("", encoding="utf-8")

    command, cwd = monitor_command(executable=app, frozen=True)

    assert command == [str(monitor)]
    assert cwd == Path(tmp_path)


def test_missing_monitor_is_a_recoverable_startup_failure(tmp_path):
    registered = []

    result = ensure_monitor_started(
        project_root=tmp_path,
        executable=tmp_path / "python.exe",
        frozen=False,
        platform_name="nt",
        stop_existing=lambda: None,
        start_scheduled=lambda: False,
        register=registered.append,
        spawn=lambda *_: None,
    )

    assert result is False
    assert registered == []
