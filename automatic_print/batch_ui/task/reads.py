"""Background read actions sharing the ERP worker lifecycle."""
from pathlib import Path

from ...runtime.cancellation import TaskCancelled
from .worker import AutomationWorker


class ReadWorker(AutomationWorker):
    def __init__(self, platform_name, kind, scope, value=None, source_status=9,
                 strategy=None):
        super().__init__('read', platform_name)
        self.kind, self.scope, self.value = kind, scope, value
        self.source_status = source_status
        self.strategy = strategy

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
        elif self.kind == 's2b_preview':
            from ...automation.api.s2b.production.preview import load_s2b_preview
            data = load_s2b_preview(self.strategy, self._report)
        else:
            raise ValueError(f'未知读取操作：{self.kind}')
        self._report('数据读取完成；正在把结果更新到界面…')
        self._deliver(self.completed, dict(type='read', kind=self.kind,
                      platform=self.platform_name,
                      scope=self.scope, value=self.value,
                      source_status=self.source_status,
                      strategy=self.strategy, data=data))

    def _completed_erp(self):
        from playwright.sync_api import sync_playwright
        from ...automation.browser.session import connect_debug_chrome
        from ...automation.providers.longfeng import find_longfeng_page
        from ...automation.providers.registry import get_erp_platform
        from ...automation.batches.supplements.completed import plan_completed_erp_batches
        from ...automation.batches.supplements.source import (
            audit_candidate_orders, load_order_snapshot,
        )
        from ...automation.api.erp import list_batch_rules
        platform = get_erp_platform(self.platform_name)
        with sync_playwright() as playwright:
            self._report(f'正在连接 {self.platform_name} 生产项页面…')
            browser = connect_debug_chrome(
                playwright,
                platform.production_items_url,
                self.cancellation.check,
                self._report,
            )
            page = find_longfeng_page(
                browser,
                self.platform_name,
                self._report,
                self.cancellation.check,
            )
            self._report('生产项页面已就绪；正在分页读取候选订单和生产图…')
            rows, details = load_order_snapshot(
                page, page_size=self.value, progress=self._report,
                source_status=self.source_status)
            self._report(
                f'候选数据读取完成：{len(rows)} 项；正在核对订单完整性…'
            )
            order_issues = audit_candidate_orders(
                page, rows, self._report, self.platform_name)
            safe_rows = [row for row in rows
                         if str(row['order_id']) not in order_issues]
            self._report('订单完整性核对完成；正在按当前规则模拟分组…')
            groups = list(plan_completed_erp_batches(
                safe_rows, details, source_status=self.source_status,
                platform_name=self.platform_name, strategy=self.strategy)
                if safe_rows else ())
            for order_id in order_issues:
                blocked_rows = [row for row in rows
                                if str(row['order_id']) == order_id]
                groups.extend(plan_completed_erp_batches(
                    blocked_rows, details, source_status=self.source_status,
                    platform_name=self.platform_name, strategy=self.strategy))
            rule_issue = ''
            try:
                self._report('分组完成；正在读取 ERP 可用批次规则…')
                self.cancellation.check()
                rules = list_batch_rules(page)
                self.cancellation.check()
            except TaskCancelled:
                raise
            except Exception:
                rules = ()
                rule_issue = ('批次规则暂时无法读取，当前计划仍可预览；'
                              '生成按钮已禁用，请稍后重新读取。')
                self._report(rule_issue)
            else:
                self._report(f'批次规则读取完成：{len(rules)} 条。')
            supplemented = tuple(str(row['id']) for row in rows
                                 if row.get('supplement_detail_list'))
            return dict(count=len(rows), groups=tuple(groups), rules=rules,
                        supplemented=supplemented, order_issues=order_issues,
                        rule_issue=rule_issue)


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
        from ...automation.batches.supplements.completed import generate_completed_groups

        platform = get_erp_platform(self.platform_name)
        with sync_playwright() as playwright:
            self._report(f'正在连接 {self.platform_name} 生产项页面…')
            browser = connect_debug_chrome(
                playwright,
                platform.production_items_url,
                self.cancellation.check,
                self._report,
            )
            page = find_longfeng_page(
                browser,
                self.platform_name,
                self._report,
                self.cancellation.check,
            )
            self._report('生产项页面已就绪；正在逐组生成并核验批次…')
            codes = generate_completed_groups(page, self.groups, self.rule_id, self._report)
            self._report(f'批次生成完成：平台确认 {len(codes)} 个批次。')
            self._deliver(
                self.completed,
                dict(type='completed_erp_generated',
                     platform=self.platform_name, codes=codes),
            )
