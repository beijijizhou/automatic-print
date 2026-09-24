"""Restricted, read-only DTF account status through the shared factory gateway."""

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from automatic_print.automation.api.ydwx.credentials import client_key
from automatic_print.automation.api.supabase_public import PUBLIC_ANON_JWT


ENDPOINT = (
    "https://bhhbztpmwlzuzbzfmsos.supabase.co/functions/v1/dtf-platform-auth"
)
def account_status():
    return _call({"action": "status"})["platforms"]


def probe_account(platform):
    return _call({"action": "probe", "platform": platform})


def _call(payload):
    key = client_key()
    try:
        return _request(payload, key)
    except HTTPError as error:
        if error.code == 401:
            refreshed = client_key(refresh_share=True)
            if refreshed and refreshed != key:
                try:
                    return _request(payload, refreshed)
                except HTTPError as retry_error:
                    raise _http_error(retry_error) from retry_error
        raise _http_error(error) from error
    except (URLError, TimeoutError, OSError) as error:
        raise RuntimeError(f"无法连接 DTF 平台账号服务：{error}") from error


def _request(payload, key):
    request = Request(
        ENDPOINT,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {PUBLIC_ANON_JWT}",
            "apikey": PUBLIC_ANON_JWT,
            "X-Automatic-Print-Key": key,
        },
    )
    with urlopen(request, timeout=35) as response:
        body = json.load(response)
    if not isinstance(body, dict):
        raise RuntimeError("DTF 平台账号服务返回格式异常。")
    return body


def _http_error(error):
    try:
        message = json.load(error).get("error") or "服务请求失败"
    except (ValueError, OSError):
        message = "服务请求失败"
    return RuntimeError(f"DTF 平台账号服务返回 {error.code}：{message}")
