from pathlib import Path
from automatic_print.runtime import application_launch


class Kernel32:
    def __init__(self, opened=0, created=1):
        self.opened = opened
        self.created = created
        self.closed = []

    def OpenMutexW(self, *_args):
        return self.opened

    def CreateMutexW(self, *_args):
        return self.created

    def CloseHandle(self, handle):
        self.closed.append(handle)


def test_application_running_closes_the_probe_handle():
    api = Kernel32(opened=42)

    assert application_launch.application_running(platform_name="nt", kernel32=api)
    assert api.closed == [42]


def test_source_launch_command_is_fixed_to_automatic_print(tmp_path):
    python = tmp_path / "python.exe"
    pythonw = tmp_path / "pythonw.exe"
    pythonw.write_text("", encoding="utf-8")
    root = tmp_path / "project"
    package = root / "automatic_print"
    package.mkdir(parents=True)
    (package / "__main__.py").write_text("", encoding="utf-8")

    command, working_directory = application_launch.application_command(
        executable=python, frozen=False, project_root=root,
    )

    assert command == [str(pythonw), "-m", "automatic_print"]
    assert working_directory == root


def test_launch_waits_for_the_main_window_receipt(monkeypatch):
    states = iter((False, False, True))
    spawned = []
    monkeypatch.setattr(
        application_launch,
        "application_command",
        lambda: (["pythonw.exe", "-m", "automatic_print"], Path("project")),
    )

    result = application_launch.launch_application(
        running=lambda: next(states),
        spawn=lambda command, cwd: spawned.append((command, cwd)),
        wait=lambda _seconds: None,
        clock=iter((0, 0, 1)).__next__,
        timeout=12,
    )

    assert result == {"launched": True, "already_running": False}
    assert spawned == [(["pythonw.exe", "-m", "automatic_print"], Path("project"))]


def test_launch_does_not_open_a_second_main_window():
    called = []

    result = application_launch.launch_application(
        running=lambda: True,
        spawn=lambda *_args: called.append(True),
    )

    assert result == {"launched": False, "already_running": True}
    assert called == []
