"""Fleet source version selection, upgrade and safe rollback UI."""

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox, QGroupBox, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from .. import (
    __command_capabilities__, __command_protocol__, __release_date__,
    __release_iteration__, __release_notes__, __version__,
)
from ..updates.source import SourceVersion, source_install
from .fleet_update_support import (
    ACTIVE, FleetCapabilityVerifier, FleetUpdateSubmitter, FleetVersionLoader,
    update_state, version_key,
)
from .fleet_update_view import release_notes_text, switch_confirmation_text, target_state
from .machine_status_format import machine_display_name, machine_slots

__all__ = ["FleetUpdatePanel", "update_state"]


class FleetUpdatePanel(QGroupBox):
    commands_submitted = Signal()

    def __init__(self, parent=None, *, auto_load=True):
        super().__init__("11 台电脑版本管理", parent)
        self.compact = False
        self.machines, self.commands, self.slots, self.selected = [], [], [], {}
        self.refreshing = False
        self.submitter = FleetUpdateSubmitter(self)
        self.submitter.completed.connect(self._completed)
        self.verifier = FleetCapabilityVerifier(self)
        self.verifier.completed.connect(self._verification_submitted)
        self.loader = FleetVersionLoader(self)
        self.loader.completed.connect(self._versions_loaded)
        self.loader.failed.connect(self._versions_failed)
        self.summary = QLabel("正在读取可用版本…")
        self.summary.setWordWrap(True)
        self.versions = QComboBox()
        self.versions.setMinimumWidth(260)
        current = SourceVersion("", __version__, __release_date__, __release_iteration__,
                                __release_notes__, __command_protocol__, __command_capabilities__)
        self.versions.addItem(current.display_version, current)
        self.versions.currentIndexChanged.connect(self._target_changed)
        self.reload_button = QPushButton("刷新版本")
        self.reload_button.clicked.connect(self.load_versions)
        self.select_all_button = QPushButton("全选待切换")
        self.select_all_button.clicked.connect(lambda: self._select(True))
        self.clear_button = QPushButton("取消全选")
        self.clear_button.clicked.connect(lambda: self._select(False))
        self.button = QPushButton("切换已选电脑")
        self.button.clicked.connect(self.start_all)
        self.table = QTableWidget(11, 4)
        self.table.setHorizontalHeaderLabels(("选择", "电脑", "当前版本", "版本状态"))
        self.table.itemChanged.connect(self._selection_changed)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(34)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setMinimumHeight(420)
        target_row = QHBoxLayout()
        target_row.addWidget(QLabel("目标版本"))
        target_row.addWidget(self.versions, 1)
        target_row.addWidget(self.reload_button)
        self.release_notes = QLabel("版本说明：当前版本没有提供说明。")
        self.release_notes.setWordWrap(True)
        self.release_notes.setTextInteractionFlags(Qt.TextSelectableByMouse)
        header = QHBoxLayout()
        header.addWidget(self.summary, 1)
        header.addWidget(self.select_all_button)
        header.addWidget(self.clear_button)
        header.addWidget(self.button)
        layout = QVBoxLayout(self)
        layout.addLayout(target_row)
        layout.addWidget(self.release_notes)
        layout.addLayout(header)
        layout.addWidget(self.table)
        self.set_data([], [])
        if auto_load:
            QTimer.singleShot(0, self.load_versions)

    def set_compact(self, compact=True):
        """Use the shared machine table instead of rendering a second 11-row table."""
        self.compact = bool(compact)
        self.setTitle("AutomaticPrint 软件版本（开发者模式）" if compact
                      else "11 台电脑版本管理")
        self.table.setVisible(not compact)
        self.select_all_button.setVisible(not compact)
        self.clear_button.setVisible(not compact)
        self._update_button()

    def target(self):
        return self.versions.currentData()

    def load_versions(self):
        if self.loader.start():
            self.reload_button.setEnabled(False)
            self.summary.setText("正在读取 origin/main 的可回滚版本…")

    def _versions_loaded(self, versions):
        selected_version = self.target().version if self.target() else __version__
        self.versions.blockSignals(True)
        self.versions.clear()
        for version in versions:
            self.versions.addItem(version.display_version, version)
        index = next((i for i, item in enumerate(versions) if item.version == selected_version), 0)
        if versions:
            self.versions.setCurrentIndex(index)
        self.versions.blockSignals(False)
        self.reload_button.setEnabled(True)
        self.selected.clear()
        self._show_release_notes()
        self.set_data(self.machines, self.commands)

    def _versions_failed(self, error):
        self.reload_button.setEnabled(True)
        self.summary.setText(f"无法读取版本历史：{error}")
        self._update_button()

    def _target_changed(self):
        self.selected.clear()
        self._show_release_notes()
        self.set_data(self.machines, self.commands)

    def _show_release_notes(self):
        self.release_notes.setText(release_notes_text(self.target()))

    def set_data(self, machines, commands):
        self.machines, self.commands = list(machines), list(commands)
        self.slots = machine_slots(self.machines, 11)
        target = self.target()
        target_version = target.version if target else __version__
        matched = registered = 0
        self.refreshing = True
        for row, machine in enumerate(self.slots):
            name = machine_display_name(machine) if machine else f"M{row + 1}"
            current, state = "—", "未接入"
            selectable = self._eligible(machine)
            if machine is not None:
                registered += 1
                current = str(machine.get("app_version") or "未知")
                state = target_state(machine, self.commands, target)
                matched += state in {"功能已确认", "已是目标版本"}
            machine_id = str((machine or {}).get("machine_id") or "")
            self.selected.setdefault(machine_id, selectable)
            choice = QTableWidgetItem()
            choice.setFlags(Qt.ItemIsSelectable | Qt.ItemIsUserCheckable |
                            (Qt.ItemIsEnabled if selectable else Qt.NoItemFlags))
            choice.setCheckState(Qt.Checked if selectable and self.selected[machine_id] else Qt.Unchecked)
            self.table.setItem(row, 0, choice)
            for column, value in enumerate((name, current, state), 1):
                self.table.setItem(row, column, QTableWidgetItem(value))
        self.refreshing = False
        self.summary.setText(f"目标 {target_version} · 已匹配 {matched}/11 · 已登记 {registered}/11")
        self._update_button()
        self.verifier.start_needed([item for item in self.slots if item], self.commands, target)

    def _eligible(self, machine):
        target = self.target()
        return bool(target and target.revision and machine and machine.get("machine_id")
                    and not machine.get("identity_conflict")
                    and str(machine.get("app_version") or "") != target.version)

    def _selection_changed(self, item):
        if self.refreshing or item.column() != 0:
            return
        machine = self.slots[item.row()]
        if self._eligible(machine):
            self.selected[str(machine["machine_id"])] = item.checkState() == Qt.Checked
        self._update_button()

    def _select(self, checked):
        for machine in self.slots:
            if self._eligible(machine):
                self.selected[str(machine["machine_id"])] = checked
        self.set_data(self.machines, self.commands)

    def _selected_targets(self):
        return [machine for machine in self.slots if self._eligible(machine)
                and self.selected.get(str(machine["machine_id"]), False)]

    def _update_button(self):
        targets, target = self._selected_targets(), self.target()
        rollbacks = target and any(version_key(item.get("app_version")) > version_key(target.version)
                                   for item in targets)
        scope = "全部待切换软件" if self.compact else "已选电脑"
        self.button.setText(f"{'回滚' if rollbacks else '切换'}{scope}（{len(targets)}）")
        ready = targets and source_install() and target and target.revision
        self.button.setEnabled(bool(ready) and not self.submitter.lock.locked() and
                               not self.has_active_updates())

    def has_active_updates(self):
        return self.verifier.lock.locked() or any(
            item.get("action") in {"source_update", "probe"}
            and item.get("status") in ACTIVE for item in self.commands
        )

    def start_all(self):
        target, targets = self.target(), self._selected_targets()
        if not target or not target.revision:
            self.summary.setText("请先刷新并选择 origin/main 中的目标版本。")
            return False
        if not targets:
            self.summary.setText("当前没有需要切换到该版本的电脑。")
            return False
        text = switch_confirmation_text(target, targets)
        if QMessageBox.question(self, "确认切换版本", text) != QMessageBox.Yes:
            self.summary.setText("已取消发布更新指令，没有修改任何电脑。")
            return False
        if self.submitter.start(targets, target.revision, target.version):
            self.button.setEnabled(False)
            self.summary.setText(f"正在向 {len(targets)} 台电脑下发版本切换指令…")
            return True
        self.summary.setText("更新指令正在下发，请等待本次操作完成。")
        return False

    def _completed(self, result):
        sent, failures = result["sent"], result["failures"]
        detail = "；".join(f"{i['machine']}：{i['error']}" for i in failures)
        self.summary.setText(f"已下发 {len(sent)} 台 · 失败 {len(failures)} 台；正在等待目标机回执。"
                             + (" " + detail if detail else ""))
        self.commands_submitted.emit()

    def _verification_submitted(self, result):
        failures = result["failures"]
        if failures:
            self.summary.setText(
                "功能检测下发失败：" + "；".join(
                    f"{item['machine']}：{item['error']}" for item in failures
                )
            )
        self.commands_submitted.emit()
