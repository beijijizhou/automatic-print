"""Zero-cloud-traffic automation pause with authenticated LAN wake-up."""

import os
from pathlib import Path
import socket
from threading import Event, Thread
from .protocol import (
    decode_dispatch_ack,
    decode_dispatch_message,
    decode_message,
    decode_payload,
    encode_dispatch_ack,
    encode_dispatch_message,
    encode_message,
)


AUTOMATION_PORT = 45873
ACK_TIMEOUT_SECONDS = 0.2


def automation_state_file():
    root = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".automatic-print")
    return root / "AutomaticPrint" / "automation-enabled"


def automation_enabled(*, target=None):
    return Path(target or automation_state_file()).exists()


def set_automation_enabled(enabled, *, target=None):
    state = Path(target or automation_state_file())
    if enabled:
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text("enabled\n", encoding="utf-8")
        return True
    state.unlink(missing_ok=True)
    return False


def broadcast_automation(enabled, *, key=None, address="255.255.255.255", port=AUTOMATION_PORT):
    message = encode_message(enabled, key=key)
    _broadcast(message, address=address, port=port)
    return set_automation_enabled(enabled)


def notify_machine(
    target_machine_id, *, command_id="", key=None,
    address="255.255.255.255", port=AUTOMATION_PORT,
    ack_timeout=ACK_TIMEOUT_SECONDS,
):
    """Wake one LAN target and return only after its signed acknowledgement."""
    message = encode_dispatch_message(
        target_machine_id, command_id=command_id, key=key,
    )
    payload = decode_dispatch_message(message, key=key)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as stream:
        stream.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        stream.settimeout(float(ack_timeout))
        for _attempt in range(3):
            stream.sendto(message, (address, int(port)))
            try:
                response, _sender = stream.recvfrom(2048)
            except (TimeoutError, socket.timeout):
                continue
            acknowledgement = decode_dispatch_ack(response, key=key)
            if acknowledgement and (
                acknowledgement.get("target_machine_id") == payload.get("target_machine_id")
                and acknowledgement.get("command_id") == payload.get("command_id")
                and acknowledgement.get("dispatch_nonce") == payload.get("nonce")
            ):
                return True
    return False


def _broadcast(message, *, address, port):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as stream:
        stream.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        for _attempt in range(3):
            stream.sendto(message, (address, int(port)))


class AutomationWakeListener:
    def __init__(
        self, *, port=AUTOMATION_PORT, apply=set_automation_enabled,
        dispatch=None, target_machine_id="",
    ):
        self.port = int(port)
        self.apply = apply
        self.dispatch = dispatch
        self.target_machine_id = str(target_machine_id)
        self.stop_event = Event()
        self.thread = None

    def start(self):
        if self.thread is None or not self.thread.is_alive():
            self.thread = Thread(target=self._run, daemon=True, name="automation-wake")
            self.thread.start()

    def stop(self):
        self.stop_event.set()

    def _run(self):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as stream:
                stream.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                stream.bind(("", self.port))
                stream.settimeout(1)
                while not self.stop_event.is_set():
                    try:
                        message, sender = stream.recvfrom(2048)
                    except TimeoutError:
                        continue
                    payload = decode_payload(message)
                    if not payload:
                        continue
                    if payload["action"] in {"enable", "disable"}:
                        self.apply(payload["action"] == "enable")
                    elif (
                        self.dispatch is not None and
                        payload.get("target_machine_id") == self.target_machine_id
                    ):
                        stream.sendto(encode_dispatch_ack(payload), sender)
                        self.dispatch(payload)
        except OSError:
            return
