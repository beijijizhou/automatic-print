"""Zero-cloud-traffic automation pause with authenticated LAN wake-up."""

import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import socket
from threading import Event, Thread
import time

from ...automation.api.gateway_credentials import shared_client_key


AUTOMATION_PORT = 45873
MAX_MESSAGE_AGE = 30


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
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as stream:
        stream.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        for _attempt in range(3):
            stream.sendto(message, (address, int(port)))
    return set_automation_enabled(enabled)


def encode_message(enabled, *, key=None, timestamp=None, nonce=None):
    payload = {
        "action": "enable" if enabled else "disable",
        "timestamp": int(time.time() if timestamp is None else timestamp),
        "nonce": nonce or secrets.token_hex(12),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    secret = str(key or shared_client_key()).encode("utf-8")
    return raw + b"." + hmac.new(secret, raw, hashlib.sha256).hexdigest().encode("ascii")


def decode_message(message, *, key=None, now=None):
    try:
        raw, signature = bytes(message).rsplit(b".", 1)
        secret = str(key or shared_client_key()).encode("utf-8")
        expected = hmac.new(secret, raw, hashlib.sha256).hexdigest().encode("ascii")
        if not hmac.compare_digest(signature, expected):
            return None
        payload = json.loads(raw.decode("utf-8"))
        current = int(time.time() if now is None else now)
        if abs(current - int(payload["timestamp"])) > MAX_MESSAGE_AGE:
            return None
        if payload.get("action") not in {"enable", "disable"}:
            return None
        return payload["action"] == "enable"
    except (KeyError, OSError, RuntimeError, TypeError, ValueError, json.JSONDecodeError):
        return None


class AutomationWakeListener:
    def __init__(self, *, port=AUTOMATION_PORT, apply=set_automation_enabled):
        self.port = int(port)
        self.apply = apply
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
                        message, _sender = stream.recvfrom(2048)
                    except TimeoutError:
                        continue
                    enabled = decode_message(message)
                    if enabled is not None:
                        self.apply(enabled)
        except OSError:
            return
