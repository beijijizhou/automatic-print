"""Authenticated desktop access to the server-side SDS factory login."""

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .credentials import client_key


DEFAULT_ENDPOINT = (
    "https://bhhbztpmwlzuzbzfmsos.supabase.co/functions/v1/ydwx-production"
)


def request_gateway(payload, timeout=120):
    key = client_key()
    endpoint = os.environ.get("AUTOMATIC_PRINT_YDWX_URL", DEFAULT_ENDPOINT).strip()
    if not endpoint:
        raise RuntimeError("亿点万象共享服务地址未配置。")
    try:
        return _request(endpoint, payload, key, timeout)
    except HTTPError as error:
        if error.code != 401:
            raise _gateway_http_error(error) from error
        refreshed = client_key(refresh_share=True)
        if refreshed and refreshed != key:
            try:
                return _request(endpoint, payload, refreshed, timeout)
            except HTTPError as retry_error:
                raise _gateway_http_error(retry_error) from retry_error
        raise _gateway_http_error(error) from error
    except (URLError, TimeoutError, OSError) as error:
        raise RuntimeError(f"无法连接亿点万象共享服务：{error}") from error


def _request(endpoint, payload, key, timeout):
    request = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Automatic-Print-Key": key,
        },
    )
    return urlopen(request, timeout=timeout)


def _gateway_http_error(error):
    try:
        message = json.load(error).get("error") or "服务请求失败"
    except (ValueError, OSError):
        message = "服务请求失败"
    return RuntimeError(f"亿点万象共享服务返回 {error.code}：{message}")
