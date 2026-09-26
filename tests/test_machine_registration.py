import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from automatic_print.ui import machine_registration


APP = QApplication.instance() or QApplication([])


class FakeWorker(QObject):
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self):
        super().__init__()
        self.calls = []

    def start(self, machine_name=None, replace=False):
        self.calls.append((machine_name, replace))
        return True


def test_conflicting_registration_requires_confirmation(monkeypatch):
    monkeypatch.setattr(machine_registration, "machine_id", lambda: "current-id")
    worker = FakeWorker()
    confirmations = []
    panel = machine_registration.MachineRegistrationPanel(
        worker=worker,
        confirm=lambda *details: confirmations.append(details) or False,
    )
    panel.registrations = [{"machine_name": "M6", "machine_id": "old-id"}]
    panel.machine.setCurrentIndex(panel.machine.findData("M6"))

    panel.request_registration()

    assert confirmations == [("M6", panel.registrations[0], None)]
    assert worker.calls == []


def test_confirmed_conflict_requests_replace(monkeypatch):
    monkeypatch.setattr(machine_registration, "machine_id", lambda: "current-id")
    worker = FakeWorker()
    panel = machine_registration.MachineRegistrationPanel(
        worker=worker, confirm=lambda *_details: True,
    )
    panel.registrations = [{"machine_name": "M6", "machine_id": "old-id"}]
    panel.machine.setCurrentIndex(panel.machine.findData("M6"))

    panel.request_registration()

    assert worker.calls == [("M6", True)]
    assert not panel.button.isEnabled()
