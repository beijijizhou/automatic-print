from unittest.mock import patch

import pytest

from automatic_print.automation.providers.registry import get_erp_platform
from automatic_print.batch_ui.task.reads import CompletedGenerateWorker, ReadWorker


@pytest.mark.parametrize('platform_name', ('隆丰', '莆田', 'Haloo'))
def test_completed_plan_reads_the_selected_erp_platform(platform_name):
    strategy = object()
    worker = ReadWorker(platform_name, 'completed_erp', 30, 30,
                        strategy=strategy)
    with patch('playwright.sync_api.sync_playwright') as playwright, \
         patch('automatic_print.automation.browser.session.connect_debug_chrome') as connect, \
         patch('automatic_print.automation.providers.longfeng.find_longfeng_page') as find, \
         patch('automatic_print.automation.batches.supplements.source.load_order_snapshot',
               return_value=([{'id': '1', 'order_id': 'order'}], {'1': {}})) as load, \
         patch('automatic_print.automation.batches.supplements.completed.plan_completed_erp_batches',
               return_value=('group',)) as plan, \
         patch('automatic_print.automation.api.erp.list_batch_rules',
               return_value=('rule',)), \
         patch('automatic_print.automation.batches.supplements.source.list_order_items',
               return_value=[{'id': '1'}]):
        result = worker._completed_erp()

    url = get_erp_platform(platform_name).production_items_url
    connect.assert_called_once_with(
        playwright.return_value.__enter__.return_value,
        url,
        worker.cancellation.check,
        worker._report,
    )
    find.assert_called_once_with(
        connect.return_value,
        platform_name,
        worker._report,
        worker.cancellation.check,
    )
    load.assert_called_once()
    assert plan.call_args.kwargs['platform_name'] == platform_name
    assert plan.call_args.kwargs['strategy'] is strategy
    assert result['groups'] == ('group',)
    assert result['rules'] == ('rule',)


def test_production_snapshot_flags_partial_orders_before_generation():
    worker = ReadWorker('隆丰', 'completed_erp', 30, 30, source_status=5)
    row = {'id': '1', 'order_id': 'order', 'status': 5}
    with patch('playwright.sync_api.sync_playwright'), \
         patch('automatic_print.automation.browser.session.connect_debug_chrome'), \
         patch('automatic_print.automation.providers.longfeng.find_longfeng_page'), \
         patch('automatic_print.automation.batches.supplements.source.load_order_snapshot',
               return_value=([row], {'1': {}})) as load, \
         patch('automatic_print.automation.batches.supplements.completed.plan_completed_erp_batches',
               return_value=('group',)) as plan, \
         patch('automatic_print.automation.api.erp.list_batch_rules', return_value=()), \
         patch('automatic_print.automation.batches.supplements.source.list_order_items',
               return_value=[row, {'id': '2', 'order_id': 'order'}]):
        result = worker._completed_erp()
    assert load.call_args.kwargs['source_status'] == 5
    assert plan.call_args.kwargs['source_status'] == 5
    assert plan.call_args.kwargs['platform_name'] == '隆丰'
    assert result['order_issues'] == {
        'order': '读取范围未覆盖整单或订单混有其他状态'}


def test_completed_plan_survives_batch_rule_module_failure():
    worker = ReadWorker('Haloo', 'completed_erp', 30, 30)
    row = {'id': '1', 'order_id': 'order'}
    with patch('playwright.sync_api.sync_playwright'), \
         patch('automatic_print.automation.browser.session.connect_debug_chrome'), \
         patch('automatic_print.automation.providers.longfeng.find_longfeng_page'), \
         patch('automatic_print.automation.batches.supplements.source.load_order_snapshot',
               return_value=([row], {'1': {}})), \
         patch('automatic_print.automation.batches.supplements.completed.plan_completed_erp_batches',
               return_value=('group',)), \
         patch('automatic_print.automation.api.erp.list_batch_rules',
               side_effect=RuntimeError('dynamic module failed')), \
         patch('automatic_print.automation.batches.supplements.source.list_order_items',
               return_value=[row]):
        result = worker._completed_erp()

    assert result['groups'] == ('group',)
    assert result['rules'] == ()
    assert '当前计划仍可预览' in result['rule_issue']


def test_bad_production_order_does_not_block_independent_matching_group():
    worker = ReadWorker('隆丰', 'completed_erp', 30, 30, source_status=5)
    rows = [
        {'id': item_id, 'order_id': order_id, 'status': 5,
         'order_composition': 1, 'qty': 1, 'logistics_sorting_code': 'USPS',
         'process_route_code': 'A00', 'style_id': 'style',
         'style_name': 'T恤', 'color': '黑色', 'size': 'M'}
        for item_id, order_id in (('1', 'safe'), ('2', 'partial'))
    ]
    details = {row['id']: {'production_images': [{'name': 'A面'}]}
               for row in rows}
    def order_rows(_page, order_id):
        selected = [row for row in rows if row['order_id'] == order_id]
        return selected if order_id == 'safe' else selected + [
            {'id': '3', 'order_id': 'partial'}]
    with patch('playwright.sync_api.sync_playwright'), \
         patch('automatic_print.automation.browser.session.connect_debug_chrome'), \
         patch('automatic_print.automation.providers.longfeng.find_longfeng_page'), \
         patch('automatic_print.automation.batches.supplements.source.load_order_snapshot',
               return_value=(rows, details)), \
         patch('automatic_print.automation.api.erp.list_batch_rules', return_value=()), \
         patch('automatic_print.automation.batches.supplements.source.list_order_items',
               side_effect=order_rows):
        result = worker._completed_erp()
    assert {group.item_ids for group in result['groups']} == {('1',), ('2',)}
    assert result['order_issues'].keys() == {'partial'}


@pytest.mark.parametrize('platform_name', ('隆丰', '莆田', 'Haloo'))
def test_completed_generation_routes_to_selected_erp_platform(platform_name):
    worker = CompletedGenerateWorker(platform_name, ('group',), 7)
    results = []
    worker.completed.connect(results.append)
    with patch('playwright.sync_api.sync_playwright') as playwright, \
         patch('automatic_print.automation.browser.session.connect_debug_chrome') as connect, \
         patch('automatic_print.automation.providers.longfeng.find_longfeng_page') as find, \
         patch('automatic_print.automation.batches.supplements.completed.generate_completed_groups',
               return_value=('batch',)) as generate:
        worker._run_action()

    url = get_erp_platform(platform_name).production_items_url
    connect.assert_called_once_with(
        playwright.return_value.__enter__.return_value,
        url,
        worker.cancellation.check,
        worker._report,
    )
    find.assert_called_once_with(
        connect.return_value,
        platform_name,
        worker._report,
        worker.cancellation.check,
    )
    generate.assert_called_once_with(find.return_value, ('group',), 7, worker._report)
    assert results == [dict(type='completed_erp_generated',
                            platform=platform_name, codes=('batch',))]
