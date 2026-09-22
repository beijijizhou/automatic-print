"""Immutable A05 size-supplement plan records."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SupplementItem:
    item_id: str
    order_id: str
    source_batch: str
    size: str
    qty: int
    existing_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class SupplementGroup:
    label: str
    items: tuple[SupplementItem, ...]

    @property
    def piece_count(self) -> int:
        return sum(item.qty for item in self.items)


@dataclass(frozen=True)
class SupplementPlan:
    source_batches: tuple[str, ...]
    groups: tuple[SupplementGroup, ...]
    existing_item_count: int = 0
    partial_mixed_order_ids: tuple[str, ...] = ()
    allow_existing_mixed: bool = False

    @property
    def item_count(self) -> int:
        return sum(len(group.items) for group in self.groups)
