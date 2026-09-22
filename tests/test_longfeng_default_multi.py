"""Default A00 route generates only received multi-item orders."""

from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from automatic_print.automation.batches.received import default_multi


def _row(item_id, route, composition, qty=1):
    return {
        "id": item_id,
        "order_id": f"order-{item_id}",
        "qty": qty,
        "process_route_code": route,
        "process_route_id": 741283 if route == "A00" else 768786,
        "order_composition": composition,
    }


def test_preview_selects_only_default_route_multi_item(monkeypatch):
    rows = [
        _row("1", "A00", 1),
        _row("2", "A00", 2, 3),
        _row("3", "A00", 3, 2),
        _row("4", "A05", 3),
    ]
    monkeypatch.setattr(default_multi, "list_all_received_items",
                        lambda _page: (rows, len(rows)))

    plan = default_multi._preview(None)

    assert plan.route_id == "741283"
    assert plan.item_quantities == (("3", 2),)
    assert plan.order_items == (("order-3", ("3",)),)
    assert (plan.received_count, plan.item_count, plan.piece_count) == (4, 1, 2)


def test_empty_multi_item_plan_disables_generation(monkeypatch):
    monkeypatch.setattr(default_multi, "list_all_received_items",
                        lambda _page: ([_row("1", "A00", 1)], 1))
    assert default_multi._preview(None).item_count == 0
    monkeypatch.setattr(default_multi, "list_all_received_items",
                        lambda _page: ([_row("2", "A05", 1)], 1))
    assert default_multi._preview(None).route_id == ""


def test_generation_rejects_partial_order(monkeypatch):
    plan = default_multi.DefaultMultiPlan(
        "741283", 2, (("a", 1), ("b", 1)), (("order", ("a", "b")),)
    )
    monkeypatch.setattr(default_multi, "list_order_items",
                        lambda _page, _order_id: [{"id": "a"}])
    with pytest.raises(RuntimeError, match="不完整"):
        default_multi._verify_whole_orders(None, plan)


def test_generation_uses_exact_filter_and_confirms_new_batch(monkeypatch):
    plan = default_multi.DefaultMultiPlan(
        "741283", 1, (("3", 2),), (("order", ("3",)),)
    )
    page = SimpleNamespace(wait_for_timeout=lambda _ms: None)
    monkeypatch.setattr("playwright.sync_api.sync_playwright",
                        lambda: nullcontext(object()))
    monkeypatch.setattr(default_multi, "connect_debug_chrome",
                        lambda *_args: object())
    monkeypatch.setattr(default_multi, "find_longfeng_page", lambda _browser: page)
    monkeypatch.setattr(default_multi, "_preview", lambda _page: plan)
    monkeypatch.setattr(default_multi, "list_batch_rules",
                        lambda _page: [SimpleNamespace(is_default=True, id="1")])
    monkeypatch.setattr(default_multi, "list_production_items",
                        lambda _page, _payload: {"total": 1})
    monkeypatch.setattr(default_multi, "list_order_items",
                        lambda _page, _order_id: [{
                            "id": "3", "status": 1,
                            "process_route_code": "A00",
                            "order_composition": 3, "qty": 2,
                        }])
    batch = {
        "code": "new", "order_composition": 3,
        "process_route_list": [{"code": "A00"}],
        "production_order_item_num": 1, "production_piece_num": 2,
        "progress": "0.0000",
    }
    batches = iter(([], [batch]))
    monkeypatch.setattr(default_multi, "list_batches",
                        lambda *_args: next(batches))
    monkeypatch.setattr(default_multi, "_production_rows", lambda *_args: [{
        "id": "3", "order_id": "order", "qty": 2,
        "production_batch_code": "new",
    }])
    requests = []
    monkeypatch.setattr(default_multi, "generate_filtered_batch",
                        lambda _page, payload, rule_id: requests.append((payload, rule_id)))

    result = default_multi.generate_default_multi(plan)

    payload, rule_id = requests[0]
    assert payload["status"] == ["1"]
    assert payload["process_route_ids"] == [741283]
    assert payload["order_compositions"] == ["3"]
    assert rule_id == "1"
    assert result.batch_codes == ("new",)
