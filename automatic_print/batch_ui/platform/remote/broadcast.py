"""Dispatch selected batches to every machine that answers a live probe."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from threading import Lock, Thread

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QMessageBox

from ....automation.api.machine_status import preflight_machine, submit_command
from ....ui.machine_status_format import machine_display_name, machine_slots
from .dispatch import load_remote_targets
from .queue import selected_batch_details, selection_text, workload_detail


def _live_probe(machine, preflight):
    return preflight(
        machine["machine_id"], str(machine.get("machine_name") or ""),
    )


class BroadcastBatchDispatcher(QObject):
    targets_loaded = Signal(object)
    probes_finished = Signal(object)
    submitted = Signal(object)
    failed = Signal(str)

    def __init__(
        self, owner, *, fetch=load_remote_targets, submit=submit_command,
        preflight=preflight_machine,
    ):
        super().__init__(owner)
        self.owner = owner
        self.fetch = fetch
        self.submit = submit
        self.preflight = preflight
        self._lock = Lock()
        self._request = None
        self._commands = []
        self._responsive = []
        self.targets_loaded.connect(self._probe_targets)
        self.probes_finished.connect(self._confirm)
        self.submitted.connect(self._show_result)
        self.failed.connect(self._failed)

    def start(self, platform, batch_numbers, settings):
        if not self._lock.acquire(blocking=False):
            return False
        details = selected_batch_details(
            getattr(self.owner, "records", []), batch_numbers,
        )
        self._request = {
            "platform": str(platform),
            "batch_numbers": list(batch_numbers),
            "batch_details": details,
            "layout_settings": asdict(settings),
            "generate_prn": True,
        }
        self._set_busy(True, "正在读取机器清单；随后逐台实时检测…")
        Thread(target=self._load, daemon=True, name="all-machine-list").start()
        return True

    def _load(self):
        try:
            self.targets_loaded.emit(self.fetch())
        except Exception as error:
            self.failed.emit(str(error))

    def _probe_targets(self, dashboard):
        rows = dashboard.get("machines") or []
        self._commands = dashboard.get("commands") or []
        candidates = [
            machine for machine in machine_slots(rows)
            if machine is not None and not machine.get("identity_conflict")
        ]
        if not candidates:
            self._finish("没有已登记且机器号不冲突的目标机器。")
            return
        self._set_busy(True, f"正在并行检测 {len(candidates)} 台机器的现场回应…")
        Thread(
            target=self._probe_all, args=(candidates,), daemon=True,
            name="all-machine-probe",
        ).start()

    def _probe_all(self, candidates):
        responsive, rejected = [], []
        with ThreadPoolExecutor(max_workers=min(11, len(candidates))) as pool:
            futures = {
                pool.submit(_live_probe, machine, self.preflight): machine
                for machine in candidates
            }
            for future in as_completed(futures):
                machine = futures[future]
                try:
                    responsive.append((machine, future.result()))
                except Exception as error:
                    rejected.append((machine, str(error)))
        responsive.sort(key=lambda pair: pair[0].get("machine_name") or "")
        rejected.sort(key=lambda pair: pair[0].get("machine_name") or "")
        self.probes_finished.emit({"responsive": responsive, "rejected": rejected})

    def _confirm(self, result):
        self._responsive = result["responsive"]
        if not self._responsive:
            names = "、".join(
                machine_display_name(machine) for machine, _error in result["rejected"]
            ) or "无"
            self._finish(f"没有机器通过实时检测：{names}。")
            return
        lines = []
        for machine, reply in self._responsive:
            live = {**machine, **(reply.get("status") or {})}
            lines.append(
                f"{machine_display_name(machine)}："
                f"{workload_detail(live, self._commands).replace(chr(10), '；')}"
            )
        if result["rejected"]:
            lines.append("未应答（不会发送）：" + "、".join(
                machine_display_name(machine)
                for machine, _error in result["rejected"]
            ))
        batches = self._request["batch_numbers"]
        summary = selection_text(self._request["batch_details"], batches)
        detail = (
            f"已实时确认 {len(self._responsive)} 台机器：\n\n"
            + "\n".join(lines)
            + f"\n\n本次发送：{self._request['platform']} · {summary} · "
              f"批次 {'、'.join(batches)}\n"
              "每台机器将各自下载、排版、生成 PRN 并加载 PrintExp；"
              "不会开始物理打印。"
        )
        answer = QMessageBox.question(
            self.owner, "确认发送到所有可应答机器", detail,
        )
        if answer != QMessageBox.Yes:
            self._finish("已取消发送；批次选择保持不变。")
            return
        self._set_busy(True, f"正在向 {len(self._responsive)} 台机器发送任务…")
        Thread(target=self._submit_all, daemon=True, name="all-machine-submit").start()

    def _submit_all(self):
        sent, errors = [], []
        with ThreadPoolExecutor(max_workers=min(11, len(self._responsive))) as pool:
            futures = {
                pool.submit(
                    self.submit, target_machine_id=machine["machine_id"],
                    **self._request,
                ): machine
                for machine, _reply in self._responsive
            }
            for future in as_completed(futures):
                machine = futures[future]
                try:
                    sent.append((machine, future.result()))
                except Exception as error:
                    errors.append((machine, str(error)))
        self.submitted.emit({"sent": sent, "errors": errors})

    def _show_result(self, result):
        sent = result["sent"]
        errors = result["errors"]
        message = f"已发送 {len(sent)} 台，失败 {len(errors)} 台。"
        if sent:
            message += " " + "、".join(
                f"{machine_display_name(machine)}:{command.get('id')}"
                for machine, command in sent
            )
        if errors:
            message += " 失败：" + "、".join(
                f"{machine_display_name(machine)}:{error}"
                for machine, error in errors
            )
        self._finish(message)
        QMessageBox.information(self.owner, "全部机器发送结果", message)

    def _failed(self, message):
        self._finish(f"批量机器检测或发送失败：{message}")
        QMessageBox.critical(self.owner, "全部机器发送失败", str(message))

    def _finish(self, message):
        self._request = None
        self._responsive = []
        if self._lock.locked():
            self._lock.release()
        self._set_busy(False, message)

    def _set_busy(self, busy, message):
        self.owner.remote_dispatch_button.setEnabled(not busy)
        self.owner.remote_broadcast_button.setEnabled(not busy)
        self.owner.remote_dispatch_status.setText(message)
