from unittest.mock import patch

import pytest

from automatic_print.automation.providers.registry import get_erp_platform
from automatic_print.batch_ui.task.reads import CompletedGenerateWorker, ReadWorker


@pytest.mark.parametrize('platform_name', ('隆丰', '莆田', 'Haloo'))
def test_completed_plan_reads_the_selected_erp_platform(platform_name):
    worker = ReadWorker(platform_name, 'completed_erp', 30, 30)
    with patch('playwright.sync_api.sync_playwright') as playwright, \
         patch('automatic_print.automation.browser.session.connect_debug_chrome') as connect, \
         patch('automatic_print.automation.providers.longfeng.find_longfeng_page') as find, \
         patch('automatic_print.automation.batches.completed.load_completed_erp_snapshot',
               return_value=([{'id': '1'}], {'1': {}})) as load, \
         patch('automatic_print.automation.batches.completed.plan_completed_erp_batches',
               return_value=('group',)) as plan, \
         patch('automatic_print.automation.api.erp.list_batch_rules',
               return_value=('rule',)):
        result = worker._completed_erp()

    url = get_erp_platform(platform_name).production_items_url
    connect.assert_called_once_with(playwright.return_value.__enter__.return_value, url)
    find.assert_called_once_with(connect.return_value, platform_name)
    load.assert_called_once()
    plan.assert_called_once()
    assert result['groups'] == ('group',)
    assert result['rules'] == ('rule',)


@pytest.mark.parametrize('platform_name', ('隆丰', '莆田', 'Haloo'))
def test_completed_generation_routes_to_selected_erp_platform(platform_name):
    worker = CompletedGenerateWorker(platform_name, ('group',), 7)
    results = []
    worker.completed.connect(results.append)
    with patch('playwright.sync_api.sync_playwright') as playwright, \
         patch('automatic_print.automation.browser.session.connect_debug_chrome') as connect, \
         patch('automatic_print.automation.providers.longfeng.find_longfeng_page') as find, \
         patch('automatic_print.automation.batches.completed.generate_completed_groups',
               return_value=('batch',)) as generate:
        worker._run_action()

    url = get_erp_platform(platform_name).production_items_url
    connect.assert_called_once_with(playwright.return_value.__enter__.return_value, url)
    find.assert_called_once_with(connect.return_value, platform_name)
    generate.assert_called_once_with(find.return_value, ('group',), 7, worker._report)
    assert results == [dict(type='completed_erp_generated',
                            platform=platform_name, codes=('batch',))]
