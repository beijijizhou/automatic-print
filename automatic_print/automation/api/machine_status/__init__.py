"""Supabase-backed machine heartbeat API."""

from .client import (
    get_machine_registration, list_machines, register_machine, report_machine,
    set_machine_availability,
)
from .commands import claim_control, list_commands, submit_command, submit_probe
from .preflight import MachinePreflightError, preflight_machine
from .reporter import MachineStatusReporter

__all__ = [
    "MachineStatusReporter",
    "claim_control",
    "list_commands",
    "list_machines",
    "get_machine_registration",
    "register_machine",
    "report_machine",
    "set_machine_availability",
    "submit_command",
    "submit_probe",
    "MachinePreflightError",
    "preflight_machine",
]
