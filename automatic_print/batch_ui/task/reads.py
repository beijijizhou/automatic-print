"""Background read actions sharing the ERP worker lifecycle."""
from pathlib import Path

from .worker import AutomationWorker


class ReadWorker(AutomationWorker):
    def __init__(self, platform_name, kind, scope, value=None, source_status=9):
        super().__init__('read', platform_name)
        self.kind, self.scope, self.value = kind, scope, value
        self.source_status = source_status

    def _run_action(self):
        self._report('正在读取数据，请稍候…')
        if self.kind == 'local_batches':
            from ...automation.batches.local import discover_local_batches
            data = discover_local_batches(Path(self.scope[0]), self.platform_name)
        elif self.kind == 'image_names':
            from ..local.scanning import image_name_rows
            data = image_name_rows(Path(self.value))
        elif self.kind == 'completed_erp':
            data = self._completed_erp()
        else:
            raise ValueError(f'未知读取操作：{self.kind}')
        self._deliver(self.completed, dict(type='read', kind=self.kind,
                      platform=self.platform_name,
                      scope=self.scope, value=self.value,
                      source_status=self.source_status, data=data))

    def _completed_erp(self):
        from playwright.sync_api import sync_playwright
        from ...automation.browser.session import connect_debug_chrome
        from ...automation.providers.longfeng import find_longfeng_page
        from ...automation.providers.registry import get_erp_platform
        from ...automation.batches.completed import plan_completed_erp_batches
        from ...automation.batches.source import (
            audit_candidate_orders, load_order_snapshot,
        )
        from ...automation.api.erp import list_batch_rules
        platform = get_erp_platform(self.platform_name)
        with sync_playwright() as playwright:
            browser = connect_debug_chrome(playwright, platform.production_items_url)
            page = find_longfeng_page(browser, self.platform_name)
            rows, details = load_order_snapshot(
                page, page_size=self.value, progress=self._report,
                source_status=self.source_status)
            order_issues = audit_candidate_orders(page, rows, self._report)
            safe_rows = [row for row in rows
                         if str(row['order_id']) not in order_issues]
            groups = list(plan_completed_erp_batches(
                safe_rows, details, source_status=self.source_status)
                if safe_rows else ())
            for order_id in order_issues:
                blocked_rows = [row for row in rows
                                if str(row['order_id']) == order_id]
                groups.extend(plan_completed_erp_batches(
                    blocked_rows, details, source_status=self.source_status))
            rules = list_batch_rules(page)
            supplemented = tuple(str(row['id']) for row in rows
                                 if row.get('supplement_detail_list'))
            return dict(count=len(rows), groups=tuple(groups), rules=rules,
                        supplemented=supplemented, order_issues=order_issues)


class CompletedGenerateWorker(AutomationWorker):
    def __init__(self, platform_name, groups, rule_id):
        super().__init__('generate_completed_erp', platform_name)
        self.groups = tuple(groups)
        self.rule_id = rule_id

    def _run_action(self):
        from playwright.sync_api import sync_playwright
        from ...automation.browser.session import connect_debug_chrome
        from ...automation.providers.longfeng import find_longfeng_page
        from ...automation.providers.registry import get_erp_platform
        from ...automation.batches.completed import generate_completed_groups

        platform = get_erp_platform(self.platform_name)
        with sync_playwright() as playwright:
            browser = connect_debug_chrome(playwright, platform.production_items_url)
            page = find_longfeng_page(browser, self.platform_name)
            codes = generate_completed_groups(page, self.groups, self.rule_id, self._report)
            self.completed.emit(dict(type='completed_erp_generated',
                                     platform=self.platform_name, codes=codes))
