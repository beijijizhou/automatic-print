from automatic_print.automation.batches.supplements.source import audit_candidate_orders


def test_candidate_order_audit_reports_changed_and_partial_orders(monkeypatch):
    rows = [
        {'id': '1', 'order_id': 'a', 'status': 5, 'qty': 2},
        {'id': '2', 'order_id': 'b', 'status': 5, 'qty': 1},
    ]
    actual = {
        'a': [{**rows[0], 'qty': 3}],
        'b': [rows[1], {'id': '3', 'order_id': 'b', 'status': 5}],
    }
    monkeypatch.setattr(
        'automatic_print.automation.batches.supplements.source.list_order_items',
        lambda _page, order_id: actual[order_id],
    )
    reports = []

    issues = audit_candidate_orders(None, rows, reports.append)

    assert issues == {
        'a': '订单状态、数量或分组字段已变化',
        'b': '读取范围未覆盖整单或订单混有其他状态',
    }
    assert reports == ['[1/2] 核对候选订单 a', '[2/2] 核对候选订单 b']


def test_production_special_routes_are_blocked_from_generic_supplement(monkeypatch):
    rows = [
        {'id': '1', 'order_id': 'a', 'status': 5,
         'process_route_code': 'A05', 'order_composition': 1},
        {'id': '2', 'order_id': 'b', 'status': 5,
         'process_route_code': 'A00', 'order_composition': 3},
    ]
    monkeypatch.setattr(
        'automatic_print.automation.batches.supplements.source.list_order_items',
        lambda _page, order_id: [row for row in rows if row['order_id'] == order_id],
    )
    issues = audit_candidate_orders(None, rows)
    assert issues['a'].startswith('A05 无印花')
    assert issues['b'].startswith('A00 多项多件')


def test_longfeng_completed_non_default_route_is_not_a_candidate(monkeypatch):
    row = {'id': '1', 'order_id': 'a', 'status': 9,
           'process_route_code': 'A05', 'order_composition': 1}
    monkeypatch.setattr(
        'automatic_print.automation.batches.supplements.source.list_order_items',
        lambda _page, _order_id: [row],
    )
    issues = audit_candidate_orders(None, [row], platform_name='隆丰')
    assert 'A00 默认工艺路线' in issues['a']


def test_haloo_route_is_not_checked_as_longfeng_a00(monkeypatch):
    row = {'id': '1', 'order_id': 'a', 'status': 9,
           'process_route_code': 'CVC面料', 'order_composition': 1}
    monkeypatch.setattr(
        'automatic_print.automation.batches.supplements.source.list_order_items',
        lambda _page, _order_id: [row],
    )
    assert audit_candidate_orders(None, [row], platform_name='Haloo') == {}
