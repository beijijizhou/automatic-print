"""Lightweight command polling and isolated worker-process launch."""

import os
from pathlib import Path
import subprocess
import sys
from time import monotonic

from ..machine_status.commands import claim_command, update_command


class CommandDispatcher:
    def __init__(self, poll_seconds=5, claim=claim_command, spawn=None):
        self.poll_seconds = float(poll_seconds)
        self.claim = claim
        self.spawn = spawn or spawn_command_runner
        self.next_poll = 0.0
        self.process = None
        self.command_id = None

    def tick(self, clock=monotonic):
        if self.process is not None:
            result = self.process.poll()
            if result is None:
                return
            command_id = self.command_id
            self.process = None
            self.command_id = None
            if result:
                _safe_fail(command_id, f"远程任务进程退出，代码 {result}")
        now = clock()
        if now < self.next_poll:
            return
        self.next_poll = now + self.poll_seconds
        command = self.claim(timeout=4)
        if not command:
            return
        self.command_id = str(command["id"])
        try:
            self.process = self.spawn(self.command_id)
        except Exception as error:
            _safe_fail(self.command_id, f"无法启动远程任务：{error}")
            self.command_id = None


def spawn_command_runner(command_id):
    if getattr(sys, "frozen", False):
        executable = Path(sys.executable).with_name("AutomaticPrint.exe")
        arguments = [str(executable), "--remote-command", str(command_id)]
    else:
        executable = Path(sys.executable)
        if executable.name.casefold() == "pythonw.exe":
            console_python = executable.with_name("python.exe")
            if console_python.exists():
                executable = console_python
        arguments = [str(executable), "-m", "automatic_print", "--remote-command", str(command_id)]
    return subprocess.Popen(
        arguments,
        cwd=str(Path.cwd()),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        env=os.environ.copy(),
    )


def _safe_fail(command_id, message):
    if not command_id:
        return
    try:
        update_command(command_id, "failed", phase="远程任务未启动", error_message=message)
    except Exception:
        pass
