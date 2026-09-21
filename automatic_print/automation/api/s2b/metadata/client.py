"""Read normalized S2B batch metadata from the shared after-sales gateway."""
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from automatic_print.automation.api.gateway_credentials import gateway_client_key
from automatic_print.automation.api.ydwx.credentials import client_key as shared_client_key


DEFAULT_TIMEOUT_SECONDS = 20
DEFAULT_ENDPOINT = (
    "https://bhhbztpmwlzuzbzfmsos.supabase.co/functions/v1/s2b-batch-info"
)


class S2BBatchInfoError(RuntimeError):
    pass


def gateway_config():
    packaged_key = gateway_client_key()
    try:
        key = packaged_key or shared_client_key()
    except RuntimeError:
        key = ""
    return (
        os.environ.get(
            "AUTOMATIC_PRINT_S2B_BATCH_INFO_URL", DEFAULT_ENDPOINT
        ).strip(),
        key,
    )


def fetch_s2b_batch_info(
    batch_number,
    account="DTF",
    endpoint=None,
    access_key=None,
    timeout=DEFAULT_TIMEOUT_SECONDS,
):
    body = call_s2b_gateway(
        {
            "account": str(account).strip().upper() or "DTF",
            "batch_number": str(batch_number).strip().upper(),
        },
        endpoint=endpoint,
        access_key=access_key,
        timeout=timeout,
    )
    if not isinstance(body.get("records"), list):
        raise S2BBatchInfoError("共享 S2B 批次服务返回格式异常")
    return body


def call_s2b_gateway(
    payload,
    *,
    endpoint=None,
    access_key=None,
    timeout=DEFAULT_TIMEOUT_SECONDS,
):
    configured_url, configured_key = gateway_config()
    endpoint = str(endpoint or configured_url).strip()
    access_key = str(access_key or configured_key).strip()
    if not endpoint:
        raise S2BBatchInfoError("尚未配置共享 S2B 批次信息服务")
    payload = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if access_key:
        headers["X-Automatic-Print-Key"] = access_key
    request = Request(
        endpoint,
        data=payload,
        method="POST",
        headers=headers,
    )
    try:
        with urlopen(request, timeout=float(timeout)) as response:
            body = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        if error.code == 401 and access_key == configured_key:
            refreshed = shared_client_key(refresh_share=True)
            if refreshed and refreshed != access_key:
                request.add_header("X-Automatic-Print-Key", refreshed)
                try:
                    with urlopen(request, timeout=float(timeout)) as response:
                        body = json.loads(response.read().decode("utf-8"))
                except HTTPError as retry_error:
                    raise S2BBatchInfoError(
                        f"S2B 批次服务返回 {retry_error.code}："
                        f"{_error_message(retry_error.read())}"
                    ) from retry_error
                if not isinstance(body, dict):
                    raise S2BBatchInfoError("共享 S2B 服务返回格式异常")
                return body
        message = _error_message(error.read())
        raise S2BBatchInfoError(
            f"S2B 批次服务返回 {error.code}：{message}"
        ) from error
    except (URLError, TimeoutError, OSError, ValueError) as error:
        raise S2BBatchInfoError(f"无法连接共享 S2B 批次服务：{error}") from error
    if not isinstance(body, dict):
        raise S2BBatchInfoError("共享 S2B 服务返回格式异常")
    return body


def _error_message(raw):
    try:
        body = json.loads(raw.decode("utf-8"))
        return str(body.get("error") or body.get("message") or "请求失败")
    except Exception:
        return "请求失败"
