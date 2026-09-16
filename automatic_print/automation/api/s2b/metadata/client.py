"""Read normalized S2B batch metadata from the shared after-sales gateway."""
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_TIMEOUT_SECONDS = 20
DEFAULT_ENDPOINT = (
    "https://bhhbztpmwlzuzbzfmsos.supabase.co/functions/v1/s2b-batch-info"
)


class S2BBatchInfoError(RuntimeError):
    pass


def gateway_config():
    packaged_key = ""
    try:
        from ..deployment import S2B_BATCH_INFO_KEY
        packaged_key = str(S2B_BATCH_INFO_KEY).strip()
    except ImportError:
        pass
    return (
        os.environ.get(
            "AUTOMATIC_PRINT_S2B_BATCH_INFO_URL", DEFAULT_ENDPOINT
        ).strip(),
        os.environ.get(
            "AUTOMATIC_PRINT_S2B_BATCH_INFO_KEY", packaged_key
        ).strip(),
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
    if not endpoint or not access_key:
        raise S2BBatchInfoError("尚未配置共享 S2B 批次信息服务")
    payload = json.dumps(payload).encode("utf-8")
    request = Request(
        endpoint,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Automatic-Print-Key": access_key,
        },
    )
    try:
        with urlopen(request, timeout=float(timeout)) as response:
            body = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
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
