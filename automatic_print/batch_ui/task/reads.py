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
        platform = get_erp_platform('Haloo')
        with sync_playwright() as playwright:
            browser = connect_debug_chrome(playwright, platform.production_items_url)
            page = find_longfeng_page(browser, 'Haloo')
            rows, details = load_completed_haloo_snapshot(
                page, page_size=self.value, progress=self._report)
            groups = plan_completed_haloo_batches(rows, details)
            return dict(count=len(rows), groups=groups)
