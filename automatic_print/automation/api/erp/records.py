"""Convert ERP batch API rows into platform-neutral production records."""
import re
from dataclasses import dataclass
from datetime import datetime

from .gateway import production_batch_frame


@dataclass(frozen=True)
class BatchRecord:
    batch_number: str
    item_count: int
    piece_count: int
    batch_type: str
    created_at: str
    production_images_ready: bool


def records_from_rows(page, api_rows, ready_codes=None) -> list[BatchRecord]:
    ready_codes = ready_codes or set()
    frame = production_batch_frame(page)
    visible_text = {
        match.group(1): text
        for text in frame.locator('tbody tr:visible').all_inner_texts()
        if (match := re.search(r'\b(\d{12})\b', text))
    }
    composition_names = {
        '1': '单项单件', '2': '单项多件', '3': '多项多件',
    }
    records = []
    for row in api_rows:
        created = row.get('created')
        created_text = (
            datetime.fromtimestamp(int(created) / 1000).strftime(
                '%Y-%m-%d %H:%M:%S') if created else ''
        )
        code = str(row.get('code') or '')
        row_text = visible_text.get(code, '')
        ready = (row_text.count('下载') >= 3 and '生成成功' in row_text
                 ) or code in ready_codes
        records.append(BatchRecord(
            batch_number=code,
            item_count=int(row.get('production_order_item_num') or 0),
            piece_count=int(row.get('production_piece_num') or 0),
            batch_type=composition_names.get(
                str(row.get('order_composition') or ''), '其他'),
            created_at=created_text,
            production_images_ready=ready,
        ))
    return records
