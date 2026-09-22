"""S2B production-batch queries and production-image export requests."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class S2BProductionBatch:
    batch_number: str
    item_count: int
    piece_count: int
    name: str
    created_at: str
    personnel_label: str = ""


def parse_production_rows(payload: dict) -> list[S2BProductionBatch]:
    data = payload.get("data") if isinstance(payload, dict) else None
    rows = data.get("data", ()) if isinstance(data, dict) else ()
    if isinstance(payload, dict) and isinstance(payload.get("records"), list):
        rows = payload["records"]
    batches = []
    for row in rows:
        batch_number = str(row.get("batch_number") or "").strip()
        if not batch_number:
            continue
        progress = row.get("progress") if isinstance(row.get("progress"), dict) else {}
        piece_count = _number(
            row.get("piece_count"), progress.get("total_num"),
            row.get("total_num"), row.get("num"),
        )
        item_count = _number(
            row.get("item_count"), progress.get("total_print_num"),
            row.get("item_num"), piece_count,
        )
        batches.append(S2BProductionBatch(
            batch_number=batch_number,
            item_count=item_count,
            piece_count=piece_count,
            name=str(row.get("name") or "S2B生产批次"),
            created_at=str(row.get("created_at") or row.get("created_date") or ""),
            personnel_label=str(row.get("personnel_label") or "").strip(),
        ))
    return batches


def list_s2b_production_batches(page=None) -> list[S2BProductionBatch]:
    if page is None:
        from .gateway import list_batches
        return parse_production_rows(list_batches())
    from .downloads import _api
    payload = {
        "status": "",
        "order_codes": [],
        "third_order_ids": "",
        "names": "",
        "batch_numbers": "",
        "order_product_line_ids": "",
        "assign_user_id": -2,
        "page": 1,
        "per_page": 100,
    }
    return parse_production_rows(_api(
        page, "POST", "/factory/orderProductBatchNumber/index", payload
    ))


def request_production_image_export(page, batch_numbers: list[str]) -> None:
    from .downloads import _api
    path = (
        "/factory/orderProductBatchNumber/exportProductionImage"
        if len(batch_numbers) == 1
        else "/factory/orderProductBatchNumber/batchExportProductionImage"
    )
    _api(page, "POST", path, {
        "batch_number": ",".join(batch_numbers),
        "type": 1,
    })


def wait_for_ready_exports(page, batch_numbers, progress, wait_seconds=600):
    from .downloads import _latest_exports, _report
    latest = _latest_exports(page)
    missing = [batch for batch in batch_numbers if batch not in latest]
    if missing:
        _report(progress, f"正在发起 {len(missing)} 个 S2B 批次的生产图导出…")
        request_production_image_export(page, missing)
    attempts = wait_seconds // 2
    for attempt in range(attempts + 1):
        latest = _latest_exports(page)
        if all(latest.get(batch) and latest[batch].ready for batch in batch_numbers):
            return [latest[batch] for batch in batch_numbers]
        if attempt < attempts:
            pending = sum(
                not latest.get(batch) or not latest[batch].ready
                for batch in batch_numbers
            )
            _report(progress, f"S2B 正在生成生产图，等待 {pending} 个批次…")
            page.wait_for_timeout(2_000)
    raise RuntimeError("S2B 生产图在 10 分钟内未生成完成，请到导出记录检查状态。")


def _number(*values) -> int:
    for value in values:
        try:
            if value not in (None, ""):
                return int(value)
        except (TypeError, ValueError):
            continue
    return 0
