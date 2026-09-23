"""Read and audit production-item sources before planning batches."""

from ...api.erp.items import (
    list_order_items, list_production_items, production_item_images,
    production_item_payload,
)


PRODUCTION_STATUS = 5
COMPLETED_STATUS = 9
SUPPLEMENT_SOURCES = (PRODUCTION_STATUS, COMPLETED_STATUS)


ORDER_FIELDS = (
    'status', 'qty', 'logistics_sorting_code', 'order_composition',
    'production_batch_code', 'process_route_code', 'process_route_id',
    'style_id', 'color', 'size', 'has_supplement',
)


def load_order_snapshot(page, *, page_size: int = 200, progress=None,
                        source_status: int = COMPLETED_STATUS):
    """Read a bounded source snapshot and exact image-side details."""
    if not 1 <= page_size <= 200:
        raise ValueError('订单测试快照每次只允许读取 1–200 项。')
    if source_status not in SUPPLEMENT_SOURCES:
        raise ValueError('补单订单入口必须是生产中或已完成。')
    payload = production_item_payload(status=(str(source_status),), page_size=page_size)
    rows = list(list_production_items(page, payload).get('list') or [])
    details = {}
    for index, row in enumerate(rows, 1):
        if progress:
            progress(f'[{index}/{len(rows)}] 正在读取实际生产图面别')
        details[str(row['id'])] = production_item_images(page, str(row['id']))
    return rows, details


def special_strategy_issue(rows) -> str:
    if any(str(row.get('status')) == '5' and
           str(row.get('process_route_code')) == 'A05' for row in rows):
        return 'A05 无印花须使用按尺码专用补单策略'
    if any(str(row.get('status')) == '5' and
           str(row.get('process_route_code')) == 'A00' and
           str(row.get('order_composition')) == '3' for row in rows):
        return 'A00 多项多件须保持整单并使用专用策略'
    return ''


def audit_candidate_orders(page, rows, progress=None) -> dict[str, str]:
    by_order = {}
    for row in rows:
        by_order.setdefault(str(row['order_id']), {})[str(row['id'])] = row
    issues = {}
    for index, (order_id, expected) in enumerate(by_order.items(), 1):
        if progress:
            progress(f'[{index}/{len(by_order)}] 核对候选订单 {order_id}')
        try:
            actual_rows = list_order_items(page, order_id)
            actual = {str(row['id']): row for row in actual_rows}
            if len(actual) != len(actual_rows) or actual.keys() != expected.keys():
                issues[order_id] = '读取范围未覆盖整单或订单混有其他状态'
            elif any(
                str(before.get(field) or '') != str(actual[item_id].get(field) or '')
                for item_id, before in expected.items() for field in ORDER_FIELDS
            ):
                issues[order_id] = '订单状态、数量或分组字段已变化'
            elif issue := special_strategy_issue(expected.values()):
                issues[order_id] = issue
        except Exception as error:
            issues[order_id] = f'整单核验失败：{error}'
    return issues
