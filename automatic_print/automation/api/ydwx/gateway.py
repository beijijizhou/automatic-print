"""Authenticated desktop access to the server-side SDS factory login."""

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from automatic_print.automation.api.gateway_credentials import gateway_client_key


DEFAULT_ENDPOINT = (
    "https://bhhbztpmwlzuzbzfmsos.supabase.co/functions/v1/ydwx-production"
)


def request_gateway(payload, timeout=120):
    key = gateway_client_key()
    endpoint = os.environ.get("AUTOMATIC_PRINT_YDWX_URL", DEFAULT_ENDPOINT).strip()
    if not endpoint or not key:
        raise RuntimeError("亿点万象共享登录服务尚未配置；请配置服务地址和客户端访问密钥。")
    request = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Automatic-Print-Key": key,
        },
    )
    try:
        return urlopen(request, timeout=timeout)
    except HTTPError as error:
        try:
            message = json.load(error).get("error") or "服务请求失败"
        except (ValueError, OSError):
            message = "服务请求失败"
        raise RuntimeError(f"亿点万象共享服务返回 {error.code}：{message}") from error
    except (URLError, TimeoutError, OSError) as error:
        raise RuntimeError(f"无法连接亿点万象共享服务：{error}") from error
