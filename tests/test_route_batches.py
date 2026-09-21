from types import SimpleNamespace

import pytest

from automatic_print.automation.batches import routes


class _Frame:
    def locator(self, _selector):
        return SimpleNamespace(
            all_inner_texts=lambda: (
                "A05-无印花", "A04-UV工艺路线", "A00-默认工艺路线"
            ),
            count=lambda: 0,
        )


def test_route_preview_uses_exact_a05_and_all_page_options(monkeypatch):
    rows = [
        {"process_route_code": "A05", "process_route_id": 768786,
         "production_batch_id": None, "order_id": "a", "qty": 2},
        {"process_route_code": "A05", "process_route_id": 768786,
         "production_batch_id": None, "order_id": "b", "qty": 3},
        {"process_route_code": "A00", "process_route_id": 741283,
         "production_batch_id": None},
    ]
    selected = []
    monkeypatch.setattr(routes, "_select_received", lambda _page: None)
    monkeypatch.setattr(routes, "production_frame", lambda _page: _Frame())
    monkeypatch.setattr(routes, "list_all_received_items", lambda _page: (rows, 3))
    monkeypatch.setattr(routes, "_select_filter", lambda _frame, name, label:
                        selected.append((name, label)))
    monkeypatch.setattr(routes, "_run_search", lambda _frame: None)
    monkeypatch.setattr(routes, "_filtered_result_count", lambda _frame: 2)

    plan = routes._preview(object(), "A05-无印花")

    assert plan.routes == (
        "A05-无印花", "A04-UV工艺路线", "A00-默认工艺路线"
    )
    assert (plan.route_id, plan.item_count, plan.all_received_count) == (
        "768786", 2, 3
    )
    assert (plan.order_count, plan.piece_count) == (2, 5)
    assert plan.order_details == (("a", 1, 2), ("b", 1, 3))
    assert selected == [("工艺路线", "A05-无印花")]


def test_route_preview_rejects_count_mismatch(monkeypatch):
    monkeypatch.setattr(routes, "_select_received", lambda _page: None)
    monkeypatch.setattr(routes, "production_frame", lambda _page: _Frame())
    monkeypatch.setattr(routes, "list_all_received_items", lambda _page: ([
        {"process_route_code": "A05", "process_route_id": 768786}
    ], 1))
    monkeypatch.setattr(routes, "_select_filter", lambda *_args: None)
    monkeypatch.setattr(routes, "_run_search", lambda _frame: None)
    monkeypatch.setattr(routes, "_filtered_result_count", lambda _frame: 2)

    with pytest.raises(RuntimeError, match="列表显示 2 项"):
        routes._preview(object(), "A05-无印花")


def test_empty_route_remains_visible_and_cannot_generate(monkeypatch):
    class EmptyFrame(_Frame):
        def locator(self, selector):
            if selector == ".ant-empty:visible":
                return SimpleNamespace(count=lambda: 1)
            return super().locator(selector)

    monkeypatch.setattr(routes, "_select_received", lambda _page: None)
    monkeypatch.setattr(routes, "production_frame", lambda _page: EmptyFrame())
    monkeypatch.setattr(routes, "list_all_received_items", lambda _page: ([
        {"process_route_code": "A00", "process_route_id": 741283}
    ], 1))
    monkeypatch.setattr(routes, "_select_filter", lambda *_args: None)
    monkeypatch.setattr(routes, "_run_search", lambda _frame: None)
    plan = routes._preview(object(), "A05-无印花")
    assert plan.item_count == 0
    assert plan.route_id == ""
