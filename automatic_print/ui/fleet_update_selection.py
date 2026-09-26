"""Selection and readiness rules for the fleet update panel."""

from PySide6.QtCore import Qt

from ..updates.source import source_install
from .fleet_update_support import ACTIVE, version_key
from .fleet_update_verification import machine_needs_update


class FleetUpdateSelectionMixin:
    def _eligible(self, machine):
        return machine_needs_update(machine, self.commands, self.target())

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
        rollbacks = target and any(
            version_key(item.get("app_version")) > version_key(target.version)
            for item in targets
        )
        scope = "全部待切换软件" if self.compact else "已选电脑"
        self.button.setText(f"{'回滚' if rollbacks else '切换'}{scope}（{len(targets)}）")
        ready = targets and source_install() and target and target.revision
        self.button.setEnabled(bool(ready) and not self.submitter.lock.locked()
                               and not self.has_active_updates())

    def has_active_updates(self):
        return self.verifier.lock.locked() or any(
            item.get("action") in {"source_update", "probe"}
            and item.get("status") in ACTIVE for item in self.commands
        )
