"""One-shot fleet signal test used by the machine status page."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock, Thread
from time import monotonic, sleep

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QLabel, QPushButton

from automatic_print import __version__

from ..automation.api.machine_status.commands import get_command, submit_probe
from .machine_status_format import machine_slots


TERMINAL_FAILURES = {"failed", "cancelled", "expired"}


def probe_machine(
    machine, *, submit=submit_probe, fetch=get_command, deadline_seconds=12,
    poll_seconds=0.5, clock=monotonic, wait=sleep,
):
    name = str(machine.get("machine_name") or "未知")
    target = str(machine.get("machine_id") or "")
    base = {"name": name, "stored_version": str(machine.get("app_version") or "")}
    if not target:
        return {**base, "state": "error", "detail": "缺少机器 ID"}
    try:
        command = submit(target)
        command_id = str(command.get("id") or "")
        if not command_id:
            raise RuntimeError("探测请求没有返回指令编号")
        deadline = clock() + float(deadline_seconds)
        while clock() < deadline:
            current = fetch(command_id)
            status = str(current.get("status") or "")
            if status == "succeeded":
                result = current.get("result") or {}
                actual_id = str(result.get("machine_id") or "")
                actual_name = str(result.get("machine_name") or "").upper()
                if actual_id != target or actual_name != name.upper():
                    return {**base, "state": "error", "detail": "回应机器身份不匹配"}
                return {
                    **base, "state": "responded",
                    "version": str(result.get("app_version") or ""),
                    "automation_enabled": result.get("automation_enabled") is True,
                    "source_online": result.get("source_online") is True,
                }
            if status in TERMINAL_FAILURES:
                detail = current.get("error_message") or current.get("phase") or status
                return {**base, "state": "error", "detail": str(detail)}
            wait(float(poll_seconds))
        return {**base, "state": "timeout", "detail": "12 秒内未回应"}
    except Exception as error:
        return {**base, "state": "error", "detail": str(error)}


def run_machine_signal_test(machines, *, probe=probe_machine, progress=None):
    targets = [
        machine for machine in machine_slots(machines, 11)
        if machine is not None and not machine.get("identity_conflict")
    ]
    results = []
    if not targets:
        return {"total": 0, "results": [], "current_version": __version__}
    with ThreadPoolExecutor(max_workers=len(targets), thread_name_prefix="machine-probe") as pool:
        futures = {pool.submit(probe, machine): machine for machine in targets}
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            if progress:
                progress(len(results), len(targets), result)
    results.sort(key=lambda item: int(item["name"][1:]))
    return {"total": len(targets), "results": results, "current_version": __version__}


def signal_result_text(report):
    results = report.get("results") or []
    total = int(report.get("total") or 0)
    current = str(report.get("current_version") or "")
    responded = [item for item in results if item.get("state") == "responded"]
    current_count = sum(
        (item.get("version") or item.get("stored_version")) == current for item in results
    )
    old = [
        item for item in results
        if (item.get("version") or item.get("stored_version"))
        and (item.get("version") or item.get("stored_version")) != current
    ]
    missed = [item for item in results if item.get("state") != "responded"]
    lines = [
        f"信号测试完成：实时响应 {len(responded)} / {total} · 当前版本 {current_count}"
        f" · 待更新 {len(old)}"
    ]
    if responded:
        lines.append("已响应：" + "、".join(
            f"{item['name']} {item.get('version') or '版本未知'}" for item in responded
        ))
    if old:
        lines.append("待更新：" + "、".join(
            f"{item['name']} {item.get('version') or item.get('stored_version')}" for item in old
        ))
    if missed:
        lines.append("未实时响应：" + "、".join(
            f"{item['name']}（{item.get('detail') or '未知原因'}，上次版本 "
            f"{item.get('stored_version') or '未知'}）" for item in missed
        ))
    return "\n".join(lines)


class MachineSignalTester(QObject):
    progress = Signal(str)
    completed = Signal(object)

    def __init__(self, parent=None, *, run=run_machine_signal_test):
        super().__init__(parent)
        self.run = run
        self._lock = Lock()

    def start(self, machines):
        if not self._lock.acquire(blocking=False):
            return False
        Thread(
            target=self._run, args=(list(machines),), daemon=True,
            name="fleet-signal-test",
        ).start()
        return True

    def _run(self, machines):
        try:
            report = self.run(machines, progress=self._show_progress)
        except Exception as error:
            report = {"total": 0, "results": [], "error": str(error)}
        finally:
            self._lock.release()
        self.completed.emit(report)

    def _show_progress(self, finished, total, result):
        self.progress.emit(
            f"正在测试机器信号：{finished} / {total} · {result.get('name', '未知')}"
        )


class MachineSignalControl(QObject):
    def __init__(self, button, result, parent=None, *, tester=None):
        super().__init__(parent)
        self.button = button
        self.result = result
        self.machines = []
        self.tester = tester or MachineSignalTester(self)
        self.button.clicked.connect(self.start)
        self.tester.progress.connect(self.result.setText)
        self.tester.completed.connect(self.show_result)

    def set_machines(self, machines):
        self.machines = [item for item in machines if isinstance(item, dict)]

    def start(self):
        if not self.machines:
            self.result.setText("没有已登记的 M1–M11，无法测试机器信号。")
            return
        if self.tester.start(self.machines):
            self.button.setEnabled(False)
            self.result.setText("正在向已登记机器发送一次性信号测试…")

    def show_result(self, report):
        self.button.setEnabled(True)
        if report.get("error"):
            self.result.setText(f"机器信号测试失败：{report['error']}；可再次测试。")
            return
        self.result.setText(signal_result_text(report))


def install_machine_signal_control(page, header, overview_layout, tester=None):
    page.signal_button = QPushButton("测试机器信号")
    page.signal_result = QLabel("按“测试机器信号”可立即检测已登记机器，并核对当前版本。")
    page.signal_result.setWordWrap(True)
    page.signal_result.setTextInteractionFlags(Qt.TextSelectableByMouse)
    header.addWidget(page.signal_button)
    overview_layout.addWidget(page.signal_result)
    return MachineSignalControl(
        page.signal_button, page.signal_result, page, tester=tester,
    )
