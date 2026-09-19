"""Background read actions sharing the ERP worker lifecycle."""
from pathlib import Path

from .worker import AutomationWorker


class ReadWorker(AutomationWorker):
    def __init__(self, platform_name, kind, scope, value=None):
        super().__init__('read', platform_name)
        self.kind, self.scope, self.value = kind, scope, value

    def _run_action(self):
        self._report('正在读取数据，请稍候…')
        if self.kind == 'local_batches':
            from ...automation.batches.local import discover_local_batches
            data = discover_local_batches(Path(self.scope[0]), self.platform_name)
        elif self.kind == 'image_names':
            from ..local.scanning import image_name_rows
            data = image_name_rows(Path(self.value))
        elif self.kind == 'completed_haloo':
            data = self._completed_haloo()
        else:
            raise ValueError(f'未知读取操作：{self.kind}')
        self._deliver(self.completed, dict(type='read', kind=self.kind,
                      scope=self.scope, value=self.value, data=data))

    def _completed_haloo(self):
        from playwright.sync_api import sync_playwright
        from ...automation.browser.session import connect_debug_chrome
        from ...automation.providers.longfeng import find_longfeng_page
        from ...automation.providers.registry import get_erp_platform
        from ...automation.batches.completed import (
            load_completed_haloo_snapshot, plan_completed_haloo_batches,
        )
        from ...automation.api.erp import list_batch_rules
        platform = get_erp_platform('Haloo')
        with sync_playwright() as playwright:
            browser = connect_debug_chrome(playwright, platform.production_items_url)
            page = find_longfeng_page(browser, 'Haloo')
            rows, details = load_completed_haloo_snapshot(
                page, page_size=self.value, progress=self._report)
            groups = plan_completed_haloo_batches(rows, details)
            rules = list_batch_rules(page)
            supplemented = tuple(str(row['id']) for row in rows
                                 if row.get('supplement_detail_list'))
            return dict(count=len(rows), groups=groups, rules=rules,
                        supplemented=supplemented)


class CompletedGenerateWorker(AutomationWorker):
    def __init__(self, groups, rule_id):
        super().__init__('generate_completed_haloo', 'Haloo')
        self.groups = tuple(groups)
        self.rule_id = rule_id

    def _run_action(self):
        from playwright.sync_api import sync_playwright
        from ...automation.browser.session import connect_debug_chrome
        from ...automation.providers.longfeng import find_longfeng_page
        from ...automation.providers.registry import get_erp_platform
        from ...automation.batches.completed import generate_completed_groups

        platform = get_erp_platform('Haloo')
        with sync_playwright() as playwright:
            browser = connect_debug_chrome(playwright, platform.production_items_url)
            page = find_longfeng_page(browser, 'Haloo')
            codes = generate_completed_groups(page, self.groups, self.rule_id, self._report)
            self.completed.emit(dict(type='completed_haloo_generated', codes=codes))
