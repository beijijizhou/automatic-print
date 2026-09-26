"""Signed, short-lived wire messages shared by LAN and cloud wake channels."""

import hashlib
import hmac
import json
import secrets
import time

from ...automation.api.gateway_credentials import shared_client_key


MAX_MESSAGE_AGE = 30


def encode_message(enabled, *, key=None, timestamp=None, nonce=None):
    return _encode_payload({
        "action": "enable" if enabled else "disable",
        "timestamp": int(time.time() if timestamp is None else timestamp),
        "nonce": nonce or secrets.token_hex(12),
    }, key=key)


def encode_dispatch_message(
    target_machine_id, *, command_id="", key=None, timestamp=None, nonce=None,
):
    return _encode_payload({
        "action": "dispatch",
        "target_machine_id": str(target_machine_id),
        "command_id": str(command_id),
        "timestamp": int(time.time() if timestamp is None else timestamp),
        "nonce": nonce or secrets.token_hex(12),
    }, key=key)


def encode_dispatch_ack(payload, *, key=None, timestamp=None, nonce=None):
    return _encode_payload({
        "action": "dispatch_ack",
        "target_machine_id": str(payload.get("target_machine_id") or ""),
        "command_id": str(payload.get("command_id") or ""),
        "dispatch_nonce": str(payload.get("nonce") or ""),
        "timestamp": int(time.time() if timestamp is None else timestamp),
        "nonce": nonce or secrets.token_hex(12),
    }, key=key)


def decode_message(message, *, key=None, now=None):
    payload = decode_payload(message, key=key, now=now)
    if not payload or payload.get("action") not in {"enable", "disable"}:
        return None
    return payload["action"] == "enable"


def decode_dispatch_message(message, *, key=None, now=None):
    payload = decode_payload(message, key=key, now=now)
    if not payload or payload.get("action") != "dispatch":
        return None
    return payload if payload.get("target_machine_id") else None


def decode_dispatch_ack(message, *, key=None, now=None):
    payload = decode_payload(message, key=key, now=now)
    if not payload or payload.get("action") != "dispatch_ack":
        return None
    return payload if payload.get("target_machine_id") and payload.get("dispatch_nonce") else None


def _encode_payload(payload, *, key=None):
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    secret = str(key or shared_client_key()).encode("utf-8")
    return raw + b"." + hmac.new(secret, raw, hashlib.sha256).hexdigest().encode("ascii")


def decode_payload(message, *, key=None, now=None):
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
        if payload.get("action") not in {"enable", "disable", "dispatch", "dispatch_ack"}:
            return None
        return payload
    except (KeyError, OSError, RuntimeError, TypeError, ValueError, json.JSONDecodeError):
        return None
