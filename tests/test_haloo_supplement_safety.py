"""Unsafe production sources cannot enter generic supplement submission."""
import pytest
from unittest.mock import patch
from automatic_print.automation.batches.supplements.completed import (
    generate_completed_groups, plan_completed_erp_batches, verify_completed_group,
)
from test_haloo_completed_batches import _detail, _row

def test_production_a05_cannot_use_generic_supplement_submission() -> None:
    row = _row('1', 'a')
    row.update(status=5, process_route_code='A05')
    group = plan_completed_erp_batches(
        [row], {'1': _detail('A面')}, source_status=5)[0]
    with patch('automatic_print.automation.api.erp.items.list_production_items',
               return_value={'list': [row], 'total': 1}):
        with pytest.raises(RuntimeError, match='A05 无印花'):
            verify_completed_group(object(), group)


def test_generation_rejects_mixed_order_sources_before_write() -> None:
    produced = _row('1', 'a')
    production = _row('2', 'b')
    production['status'] = 5
    groups = (
        plan_completed_erp_batches([produced], {'1': _detail('A面')})[0],
        plan_completed_erp_batches([production], {'2': _detail('A面')},
                                   source_status=5)[0],
    )
    with pytest.raises(ValueError, match='不同订单入口'):
        generate_completed_groups(object(), groups, 1)
