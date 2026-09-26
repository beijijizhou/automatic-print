"""One-shot fleet signal test used by the machine status page."""

from collections import Counter
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
    machine, *, submit=None, fetch=get_command, deadline_seconds=12,
    poll_seconds=0.5, clock=monotonic, wait=sleep,
):
    name = str(machine.get("machine_name") or "未知")
    target = str(machine.get("machine_id") or "")
    base = {"name": name, "stored_version": str(machine.get("app_version") or "")}
    if not target:
        return {**base, "state": "error", "detail": "缺少机器 ID"}
    try:
        command = (
            submit(target) if submit is not None
            else submit_probe(target, realtime_only=True)
        )
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
    responded = [item for item in results if item.get("state") == "responded"]
    missed = [item for item in results if item.get("state") != "responded"]
    versions = Counter(item.get("version") or "版本未知" for item in responded)
    lines = [
        f"Realtime 测试完成：已响应 {len(responded)} / {total} · 未响应 {len(missed)}"
    ]
    if versions:
        lines.append("实时版本分布：" + " · ".join(
            f"{version}（{count} 台）" for version, count in versions.most_common()
        ))
    if responded:
        lines.append("已响应机器：\n" + "　".join(
            f"{item['name']} {item.get('version') or '版本未知'}" for item in responded
        ))
    if missed:
        lines.append("未响应机器：\n" + "　".join(
            f"{item['name']} · {item.get('detail') or '未知原因'}"
            f" · 上次 {item.get('stored_version') or '版本未知'}" for item in missed
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
            f"正在通过 Realtime 测试机器：{finished} / {total} · {result.get('name', '未知')}"
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
            self.result.setText("没有已登记的 M1–M11，无法测试 Realtime 信号。")
            return
        if self.tester.start(self.machines):
            self.button.setEnabled(False)
            self.result.setText("正在绕过 UDP，通过 Supabase Realtime 测试全部已登记机器…")

    def show_result(self, report):
        self.button.setEnabled(True)
        if report.get("error"):
            self.result.setText(f"Realtime 信号测试失败：{report['error']}；可再次测试。")
            return
        self.result.setText(signal_result_text(report))


def install_machine_signal_control(page, header, overview_layout, tester=None):
    page.signal_button = QPushButton("Realtime 全机信号测试")
    page.signal_button.setToolTip("绕过局域网 UDP，只使用 Supabase Realtime Broadcast 测试 M1–M11。")
    page.signal_update_button = QPushButton("发布最新版本更新指令")
    page.signal_update_button.clicked.connect(lambda: _start_latest_update(page))
    page.signal_result = QLabel("按按钮可绕过 UDP，通过 Realtime 检测全部已登记机器并核对版本。")
    page.signal_result.setWordWrap(True)
    page.signal_result.setTextInteractionFlags(Qt.TextSelectableByMouse)
    page.signal_result.setStyleSheet("padding:10px;border:1px solid #cbd5e1;background:#f8fafc;")
    header.addWidget(page.signal_button)
    header.addWidget(page.signal_update_button)
    overview_layout.addWidget(page.signal_result)
    return MachineSignalControl(
        page.signal_button, page.signal_result, page, tester=tester,
    )


def _start_latest_update(page):
    page.sections.setCurrentWidget(page.update_section)
    panel = page.update_panel
    if panel.loader.lock.locked() or not panel.versions.count():
        panel.summary.setText("正在读取最新版本，请稍后再次点击发布更新指令。")
        return
    panel.versions.setCurrentIndex(0)
    panel._select(True)
    panel.start_all()
