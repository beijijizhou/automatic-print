"""Read the factory's dated production-task groups without changing state."""

from dataclasses import dataclass
from json import load
from .gateway import request_gateway


@dataclass(frozen=True)
class YdwxBatch:
    task_id: int
    number: str
    name: str
    date: str
    manuscript_count: int
    downloaded_count: int
    product_count: int


def parse_batches(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get("dateList"), list):
        raise ValueError("亿点万象批次响应缺少 dateList，未采用本次结果。")
    records = []
    seen = set()
    for group in payload["dateList"]:
        if not isinstance(group, dict) or not isinstance(group.get("producingTaskList"), list):
            raise ValueError("亿点万象批次分组格式异常，未采用本次结果。")
        date = str(group.get("date") or "")
        for row in group["producingTaskList"]:
            if not isinstance(row, dict):
                raise ValueError("亿点万象批次记录格式异常，未采用本次结果。")
            task_id = int(row["id"])
            number, name = str(row["no"]).strip(), str(row["name"]).strip()
            if task_id <= 0 or not number or not name or task_id in seen:
                raise ValueError("亿点万象批次身份缺失或重复，未采用本次结果。")
            seen.add(task_id)
            records.append(YdwxBatch(
                task_id, number, name, date,
                int(row.get("manuscriptNum") or 0),
                int(row.get("downNum") or 0),
                int(row.get("totalProductNum") or 0),
            ))
    return sorted(records, key=lambda row: (row.date, row.task_id), reverse=True)


def list_batches():
    with request_gateway({"action": "list"}, timeout=30) as response:
        payload = load(response)
    return parse_batches(payload)
