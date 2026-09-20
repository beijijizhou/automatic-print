import os
from types import SimpleNamespace

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import QApplication, QWidget

from automatic_print.automation.batches.completed import plan_completed_haloo_batches
from automatic_print.batch_ui.platform.completed import CompletedHalooPage


APP = QApplication.instance() or QApplication([])


def _row(item, order, *, supplemented=False):
    return dict(id=item, order_id=order, status=9, order_composition=1,
                qty=1, logistics_sorting_code='USPS', style_id='style',
                style_name='棉T恤', color='黑色', size='M',
                supplement_detail_list=[{'production_batch_code': 'old'}]
                if supplemented else [])


def test_auto_plan_button_reads_completed_items_and_selects_only_eligible_groups():
    owner = QWidget()
    owner.thread = None
    workers = []
    owner._start_worker = workers.append
    page = CompletedHalooPage(owner)

    page.plan_button.click()
    assert len(workers) == 1
    assert workers[0].kind == 'completed_haloo'
    assert workers[0].value == page.limit.value()
    assert page.auto_plan_pending

    rows = [_row('1', 'a'), _row('2', 'b', supplemented=True)]
    rows[1]['color'] = '白色'
    details = {row['id']: {'production_images': [{'name': 'A面'}]}
               for row in rows}
    groups = plan_completed_haloo_batches(rows, details)
    page.setEnabled(False)  # The worker lifecycle disables the tab during delivery.
    page.show_result(dict(scope=30, data=dict(
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
    page.show_result(dict(scope=31, data=dict(
        count=1, groups=(blocked_group,), supplemented=('2',),
        rules=[SimpleNamespace(id=7, name='默认规则', is_default=True)])))
    assert '自动候选计划 0 组' in page.summary.text()
    assert not page.selected_groups()
    assert not page.generate_button.isEnabled()
    owner.close()
