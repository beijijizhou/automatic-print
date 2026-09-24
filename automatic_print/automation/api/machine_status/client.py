"""Restricted machine-status requests through the Supabase Edge Function."""

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from automatic_print import __version__
from automatic_print.automation.api.gateway_credentials import shared_client_key
from automatic_print.automation.api.supabase_public import PUBLIC_ANON_JWT

from .identity import machine_id, machine_name


DEFAULT_ENDPOINT = (
    "https://bhhbztpmwlzuzbzfmsos.supabase.co/functions/v1/machine-status"
)


class MachineStatusError(RuntimeError):
    pass


def report_machine(status, *, endpoint=None, access_key=None, timeout=8):
    payload = {
        **status,
        "action": "report",
        "machine_id": machine_id(),
        "machine_name": machine_name(),
        "app_version": __version__,
    }
    return _call(payload, endpoint=endpoint, access_key=access_key, timeout=timeout)


def list_machines(*, endpoint=None, access_key=None, timeout=8):
    return _call(
        {"action": "list"}, endpoint=endpoint, access_key=access_key, timeout=timeout
    )["machines"]


def set_machine_availability(machine, availability, *, endpoint=None, access_key=None, timeout=8):
    value = str(availability).strip().lower()
    if value not in {"auto", "available", "unavailable"}:
        raise ValueError("机器可用性必须是自动判断、可用或不可用。")
    return _call(
        {
            "action": "set_availability",
            "target_machine_id": str(machine),
            "availability": value,
        },
        endpoint=endpoint, access_key=access_key, timeout=timeout,
    )["machine"]


def _call(payload, *, endpoint=None, access_key=None, timeout=8):
    endpoint = str(endpoint or os.environ.get(
        "AUTOMATIC_PRINT_MACHINE_STATUS_URL", DEFAULT_ENDPOINT)).strip()
    configured_key = access_key
    if configured_key is None:
        configured_key = shared_client_key()
    request = Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {PUBLIC_ANON_JWT}",
            "apikey": PUBLIC_ANON_JWT,
            "X-Automatic-Print-Key": str(configured_key).strip(),
        },
    )
    try:
        with urlopen(request, timeout=float(timeout)) as response:
            body = json.load(response)
    except HTTPError as error:
        raise MachineStatusError(
            f"机器状态服务返回 {error.code}：{_error_message(error.read())}"
        ) from error
    except (URLError, TimeoutError, OSError, ValueError) as error:
        raise MachineStatusError(f"无法连接机器状态服务：{error}") from error
    if not isinstance(body, dict):
        raise MachineStatusError("机器状态服务返回格式异常")
    return body


def _error_message(raw):
    try:
        body = json.loads(raw.decode("utf-8"))
        return str(body.get("error") or "请求失败")
    except Exception:
        return "请求失败"
