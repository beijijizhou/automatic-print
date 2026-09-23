"""Server-side S2B production actions; raw provider token never reaches clients."""
from time import sleep

from ..metadata.client import call_s2b_gateway, gateway_config


def available() -> bool:
    endpoint, key = gateway_config()
    return bool(endpoint and key)


def list_batches() -> dict:
    return _call("production_batches", page=1, per_page=100)


def refresh_login(token: str) -> dict:
    value = str(token or "").strip()
    if not value:
        raise RuntimeError("S2B 登录已失效，请重新登录")
    return _call("refresh_login", token=value)


def wait_for_exports(batch_numbers, parse, progress=None, wait_seconds=600):
    latest = _latest(parse)
    missing = [batch for batch in batch_numbers if batch not in latest]
    if missing:
        _report(progress, f"正在通过共享 S2B 服务发起 {len(missing)} 个生产图导出…")
        _call("request_export", batch_numbers=missing)
    for attempt in range(wait_seconds // 2 + 1):
        latest = _latest(parse)
        if all(latest.get(batch) and latest[batch].ready for batch in batch_numbers):
            return [latest[batch] for batch in batch_numbers]
        if attempt < wait_seconds // 2:
            pending = sum(
                not latest.get(batch) or not latest[batch].ready
                for batch in batch_numbers
            )
            _report(progress, f"S2B 正在生成生产图，等待 {pending} 个批次…")
            sleep(2)
    raise RuntimeError("S2B 生产图在 10 分钟内未生成完成，请到导出记录检查状态。")


def mark_downloaded(record_id: int) -> None:
    _call("mark_downloaded", record_id=record_id)


def _latest(parse):
    payload = _call("export_records", page=1, per_page=100)
    latest = {}
    for record in parse(payload):
        latest.setdefault(record.batch_number, record)
    return latest


def _call(action, **payload):
    return call_s2b_gateway({"account": "DTF", "action": action, **payload})


def _report(progress, message):
    if progress:
        progress(message)
