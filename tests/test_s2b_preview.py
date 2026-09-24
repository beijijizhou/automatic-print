import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget

from automatic_print.automation.api.s2b.production.preview import plan_s2b_preview
from automatic_print.automation.batches.supplements.grouping.strategy import (
    GroupingStrategy, default_strategy,
)
from automatic_print.batch_ui.platform.s2b.preview import S2BPreviewPage


APP = QApplication.instance() or QApplication([])


def _row(production, order, item, *, qty=1, color="黑色", size="M",
         product="男士纯棉烫画T恤", logistics="CBT"):
    return {
        "production_id": str(production), "order_code": order,
        "item_id": str(item), "quantity": qty, "color": color, "size": size,
        "order_total_count": qty,
        "product_name": product, "style_name": product, "logistics": logistics,
    }


def test_s2b_preview_groups_real_semantics_and_keeps_whole_orders():
    rows = [
        _row(1, "single-small", 11, size="S"),
        _row(2, "single-large", 12, size="3XL"),
        _row(3, "double", 13, product="男士纯棉烫画T恤-双面"),
        _row(4, "multi-piece", 14, qty=2),
        _row(5, "multi-item", 15),
        _row(6, "multi-item", 16, color="白色", size="XL"),
    ]
    rows[4]["order_total_count"] = 2
    rows[5]["order_total_count"] = 2
    groups = plan_s2b_preview(rows, default_strategy("S2B"))

    assert [(group.composition, group.face, group.color, group.size_group)
            for group in groups] == [
        ("单项单件", "单面", "黑色", "2XL-5XL"),
        ("单项单件", "单面", "黑色", "S-XL"),
        ("单项单件", "双面", "", ""),
        ("单项多件", "不区分面别", "", ""),
        ("多项多件", "不区分面别", "", ""),
    ]
    multi = next(group for group in groups if group.composition == "多项多件")
    assert multi.order_codes == ("multi-item",)
    assert multi.production_ids == ("5", "6")
    assert multi.item_count == 2 and multi.piece_count == 2


def test_s2b_preview_uses_optional_logistics_and_style():
    strategy = GroupingStrategy(True, True, True, True, True, True)
    rows = [_row(1, "a", 1, logistics="CBT"),
            _row(2, "b", 2, logistics="USPS")]
    groups = plan_s2b_preview(rows, strategy)
    assert {group.logistics for group in groups} == {"CBT", "USPS"}
    assert all(group.style == "男士纯棉烫画T恤" for group in groups)


def test_s2b_preview_rejects_incomplete_whole_order():
    row = _row(1, "partial", 1)
    row["order_total_count"] = 2
    try:
        plan_s2b_preview([row], default_strategy("S2B"))
    except RuntimeError as error:
        assert "返回不完整" in str(error)
    else:
        raise AssertionError("incomplete S2B order was accepted")


def test_s2b_preview_page_has_no_generation_action_and_invalidates_rules():
    owner = QWidget()
    owner.thread = None
    owner.preferences = None
    workers = []
    owner._start_worker = workers.append
    page = S2BPreviewPage(owner)
    page.load()
    assert workers[0].kind == "s2b_preview"
    assert "模拟分组" in page.read_button.text()
    assert not any("生成批次" in button.text() for button in page.findChildren(type(page.read_button)))
    page.summary.setText("旧预览")
    page.strategy_editor.controls["by_style"].setChecked(True)
    assert page.summary.text() == "规则已变化，请重新读取并模拟分组。"
    page.close()
    owner.close()
