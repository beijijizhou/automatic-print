"""Developer-only full automated and real-batch regression runner."""

import os
import sys
from pathlib import Path
from time import perf_counter

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer
from PySide6.QtWidgets import QDialog, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout

from .full_test_results import phase_summary, real_batch_file_summary


def full_test_phases(project_root=None, python_executable=None, result_root=None):
    root = Path(project_root or Path(__file__).resolve().parents[2])
    python = str(python_executable or sys.executable)
    target = Path(result_root or (Path(os.getenv("LOCALAPPDATA") or Path.home()) /
                                  "AutomaticPrint" / "full-test" / "latest"))
    powershell = str(Path(os.getenv("SystemRoot") or r"C:\Windows") /
                     "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe")
    return (
        {
            "key": "automated", "name": "完整自动测试",
            "program": python,
            "arguments": ("-m", "pytest", "-q", "-p", "no:cacheprovider"),
        },
        {
            "key": "real_batches", "name": "真实批次跨平台回归",
            "summary_file": str(target / "reports" / "suite-summary.json"),
            "program": powershell,
            "arguments": (
                "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                str(root / "windows" / "run-real-batch-suite.ps1"),
                "-ArtifactRoot", str(target / "reports"),
                "-OutputRoot", str(target / "outputs"),
                "-CacheRoot", str(target / "cache"),
            ),
        },
    )


class FullTestLogDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("开发者 · 完整测试结果")
        self.resize(880, 560)
        note = QLabel("依次运行完整自动测试和本机真实生产样本回归。真实回归覆盖 Haloo、隆丰、"
                      "莆田和 S2B，只生成测试 PNG 与核验报告，不生成、装载或发送 PRN。")
        note.setWordWrap(True)
        self.status = QLabel("尚未运行")
        self.status.setWordWrap(True)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        layout = QVBoxLayout(self)
        layout.addWidget(note)
        layout.addWidget(self.status)
        layout.addWidget(self.log, 1)

    def closeEvent(self, event):
        controller = getattr(self.parent(), "full_test_controller", None)
        if controller and controller.is_running():
            self.hide()
            event.ignore()
            return
        super().closeEvent(event)


class FullTestController(QObject):
    def __init__(self, window, button, result, parent=None, *, phases=None):
        super().__init__(parent or window)
        self.window = window
        self.button = button
        self.result = result
        self.dialog = FullTestLogDialog(window)
        self.phases = tuple(phases or full_test_phases())
        self.process = None
        self.phase_index = -1
        self.phase_results = []
        self.phase_summaries = []
        self.phase_output = ""
        self.started_at = None
        self.current_name = ""
        self.clock = QTimer(self)
        self.clock.setInterval(500)
        self.clock.timeout.connect(self._tick)
        button.clicked.connect(self.start)

    def is_running(self):
        return self.process is not None and self.process.state() != QProcess.NotRunning

    def start(self):
        self.dialog.show()
        self.dialog.raise_()
        if self.is_running() or self.window.has_active_tasks():
            self.result.setText("完整测试：已有任务运行")
            self.dialog.status.setText("已有任务运行，请等待完成后再运行完整测试。")
            return
        if getattr(sys, "frozen", False):
            self.result.setText("完整测试：需要源码环境")
            self.dialog.status.setText("安装包不包含 pytest；请在源码环境运行。")
            return
        self.phase_index = -1
        self.phase_results = []
        self.phase_summaries = []
        self.started_at = perf_counter()
        self.dialog.log.clear()
        self.button.setEnabled(False)
        self.clock.start()
        self._start_next()

    def _start_next(self):
        self.phase_index += 1
        if self.phase_index >= len(self.phases):
            self._complete()
            return
        phase = self.phases[self.phase_index]
        self.current_name = phase["name"]
        self.phase_output = ""
        self.result.setText(f"完整测试：{self.current_name}…")
        self.dialog.status.setText(
            f"第 {self.phase_index + 1} / {len(self.phases)} 步：{self.current_name}"
        )
        self.dialog.log.appendPlainText(f"\n=== {self.current_name} ===")
        process = QProcess(self)
        process.setWorkingDirectory(str(Path(__file__).resolve().parents[2]))
        process.setProcessChannelMode(QProcess.MergedChannels)
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("PYTHON_EXE", sys.executable)
        process.setProcessEnvironment(environment)
        process.readyReadStandardOutput.connect(self._read_output)
        process.finished.connect(self._phase_finished)
        self.process = process
        process.start(phase["program"], list(phase["arguments"]))
        if not process.waitForStarted(5000):
            self._record_phase(-1, f"无法启动：{process.errorString()}")

    def _read_output(self):
        if self.process is None:
            return
        text = bytes(self.process.readAllStandardOutput()).decode("utf-8", "replace")
        if text:
            self.phase_output += text
            self.dialog.log.insertPlainText(text)
            self.dialog.log.ensureCursorVisible()

    def _phase_finished(self, exit_code, _status):
        self._read_output()
        self._record_phase(int(exit_code), "")

    def _record_phase(self, exit_code, detail):
        self.phase_results.append((self.current_name, exit_code, detail))
        key = self.phases[self.phase_index]["key"]
        summary = phase_summary(key, self.phase_output)
        if key == "real_batches":
            summary = real_batch_file_summary(self.phases[self.phase_index]["summary_file"], summary)
        self.phase_summaries.append(summary)
        state = "通过" if exit_code == 0 else "失败"
        self.dialog.log.appendPlainText(f"\n{self.current_name}：{state}{' · ' + detail if detail else ''}")
        if self.process is not None:
            self.process.deleteLater()
        self.process = None
        QTimer.singleShot(0, self._start_next)

    def _tick(self):
        if self.started_at is not None:
            elapsed = perf_counter() - self.started_at
            self.dialog.status.setText(
                f"第 {self.phase_index + 1} / {len(self.phases)} 步："
                f"{self.current_name} · {elapsed:.0f} 秒"
            )

    def _complete(self):
        self.clock.stop()
        elapsed = perf_counter() - self.started_at
        failed = [name for name, code, _detail in self.phase_results if code != 0]
        if failed:
            summary = "失败：" + "、".join(failed)
            self.result.setText(f"完整测试：失败 · {elapsed:.0f} 秒")
        else:
            summary = "全部通过"
            self.result.setText(f"完整测试：全部通过 · {elapsed:.0f} 秒")
        result_detail = " · ".join(self.phase_summaries)
        self.result.setText(f"完整测试：{summary} · {result_detail} · {elapsed:.0f} 秒")
        self.dialog.status.setText(f"完整测试{summary} · {result_detail} · {elapsed:.2f} 秒；详细结果见下方日志。")
        self.button.setEnabled(True)


def install_full_test_control(window, menu):
    window.full_test_button = QPushButton("完整测试")
    window.full_test_button.setToolTip("运行完整自动测试和本机真实批次跨平台回归；不生成 PRN。")
    window.full_test_result = QLabel("完整测试：尚未运行")
    window.full_test_result.setMinimumWidth(170)
    menu.addWidget(window.full_test_button)
    menu.addWidget(window.full_test_result)
    window.full_test_controller = FullTestController(
        window, window.full_test_button, window.full_test_result,
    )
    return window.full_test_controller
