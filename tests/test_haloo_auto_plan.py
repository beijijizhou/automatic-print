import os
from types import SimpleNamespace
import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import QApplication, QLabel, QWidget

from automatic_print.automation.batches.supplements.completed import plan_completed_erp_batches
from automatic_print.automation.batches.supplements.completed import CompletedBatchGroup
from automatic_print.batch_ui.platform.completed import CompletedErpPage


APP = QApplication.instance() or QApplication([])


def _row(item, order, *, supplemented=False):
    return dict(id=item, order_id=order, status=9, order_composition=1,
                qty=1, logistics_sorting_code='USPS', style_id='style',
                style_name='棉T恤', color='黑色', size='M',
                supplement_detail_list=[{'production_batch_code': 'old'}]
                if supplemented else [])


def test_production_preview_blocks_incomplete_order_before_submission():
    owner = QWidget()
    owner.thread = None
    workers = []
    owner._start_worker = workers.append
    page = CompletedErpPage(owner, '隆丰')
    page.plan_button.click()
    assert workers[0].source_status == 5
    row = _row('1', 'partial')
    row['status'] = 5
    groups = plan_completed_erp_batches(
        [row], {'1': {'production_images': [{'name': 'A面'}]}},
        source_status=5)
    page.show_result(dict(platform='隆丰', scope=30, source_status=5,
                          data=dict(count=1, groups=groups, supplemented=(),
                                    order_issues={'partial': '整单不完整'},
                                    rules=[SimpleNamespace(id=7, name='默认规则',
                                                           is_default=True)])))
    assert not page.boxes[0].isEnabled()
    assert not page.generate_button.isEnabled()
    assert '整单异常 1 单' in page.summary.text()
    page.source.setCurrentIndex(1)
    assert page.table.rowCount() == 0
    assert not page.generate_button.isEnabled()


@pytest.mark.parametrize('platform_name', ('隆丰', '莆田', 'Haloo'))
def test_auto_plan_button_reads_completed_items_and_selects_only_eligible_groups(platform_name):
    owner = QWidget()
    owner.thread = None
    workers = []
    owner._start_worker = workers.append
    page = CompletedErpPage(owner, platform_name)
    page.source.setCurrentIndex(1)

    page.plan_button.click()
    assert len(workers) == 1
    assert workers[0].kind == 'completed_erp'
    assert workers[0].platform_name == platform_name
    assert workers[0].value == page.limit.value()
    assert page.auto_plan_pending

    rows = [_row('1', 'a'), _row('2', 'b', supplemented=True)]
    rows[1]['color'] = '白色'
    details = {row['id']: {'production_images': [{'name': 'A面'}]}
               for row in rows}
    groups = plan_completed_erp_batches(rows, details)
    page.setEnabled(False)  # The worker lifecycle disables the tab during delivery.
    page.show_result(dict(platform=platform_name, scope=30, data=dict(
        count=2, groups=groups, supplemented=('2',),
        rules=[SimpleNamespace(id=7, name='默认规则', is_default=True)])))
    page.setEnabled(True)
    page.set_actions_enabled(True)

    assert tuple(item for group in page.selected_groups()
                 for item in group.item_ids) == ('1',)
    assert page.generate_button.isEnabled()
    assert '自动候选计划 1 组' in page.summary.text()
    assert '棉T恤' in page.selection_preview.toPlainText()
    assert not page.auto_plan_pending

    page.limit.setValue(31)
    assert not page.selected_groups()
    assert not page.generate_button.isEnabled()
    assert page.selection_preview.toPlainText() == ''

    page.plan_button.click()
    blocked_group = next(group for group in groups if '2' in group.item_ids)
    page.show_result(dict(platform=platform_name, scope=31, data=dict(
        count=1, groups=(blocked_group,), supplemented=('2',),
        rules=[SimpleNamespace(id=7, name='默认规则', is_default=True)])))
    assert '自动候选计划 0 组' in page.summary.text()
    assert not page.selected_groups()
    assert not page.generate_button.isEnabled()
    owner.close()


def test_confirmed_strategy_ui_explains_unsplit_fields() -> None:
    owner = QWidget()
    owner.thread = None
    owner._start_worker = lambda _worker: None
    page = CompletedErpPage(owner, '隆丰')
    page.source.setCurrentIndex(1)
    group = CompletedBatchGroup(
        '', '单项单件', '双面', ('1',),
        item_quantities=(('1', 1),), order_ids=('a',), platform_name='隆丰')
    page.show_result(dict(platform='隆丰', scope=30, source_status=9, data=dict(
        count=1, groups=(group,), supplemented=(), order_issues={},
        rules=[SimpleNamespace(id=7, name='默认规则', is_default=True)])))

    note_text = '\n'.join(label.text() for label in page.findChildren(QLabel))
    assert '不按物流、底款或尺码拆分' in note_text
    assert page.table.item(0, 1).text() == '不分物流'
    assert page.table.item(0, 3).text() == '不按底款拆分'
    assert page.table.item(0, 4).text() == '不分颜色'
    assert page.table.item(0, 6).text() == '不分尺码'
    owner.close()
