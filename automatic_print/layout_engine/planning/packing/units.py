from __future__ import annotations

from dataclasses import dataclass

from automatic_print.layout_engine.intake.preparation.item_factory import LayoutItem
from automatic_print.layout_engine.orders.order_groups import is_double_pair


@dataclass(frozen=True)
class UnitMember:
    item: LayoutItem
    x: int
    y: int


@dataclass(frozen=True)
class UnitChoice:
    width: int
    height: int
    members: tuple[UnitMember, ...]
    rotation_cost: int


def build_units(
    items: list[list[LayoutItem]], spacing: int
) -> list[list[UnitChoice]]:
    units, index = [], 0
    while index < len(items):
        if index + 1 < len(items) and _is_double_pair(
            items[index][0], items[index + 1][0]
        ):
            units.append(_double_choices(items[index:index + 2], spacing))
            index += 2
        else:
            units.append([_single(item) for item in items[index]])
            index += 1
    return units


def optimizer_options(units):
    return [
        [
            (choice.width, choice.height, choice.rotation_cost)
            for choice in choices
        ]
        for choices in units
    ]


def _is_double_pair(first: LayoutItem, second: LayoutItem) -> bool:
    return is_double_pair(first.path, second.path)


def _single(item: LayoutItem) -> UnitChoice:
    return UnitChoice(
        item.footprint_width,
        item.footprint_height,
        (UnitMember(item, 0, 0),),
        int(bool(item.rotation_degrees)),
    )


def _double_choices(pair, spacing):
    choices = []
    for first in pair[0]:
        for second in pair[1]:
            rotations = sum(
                bool(item.rotation_degrees) for item in (first, second)
            )
            choices.extend(
                (
                    UnitChoice(
                        first.footprint_width
                        + spacing
                        + second.footprint_width,
                        max(
                            first.footprint_height,
                            second.footprint_height,
                        ),
                        (
                            UnitMember(first, 0, 0),
                            UnitMember(
                                second,
                                first.footprint_width + spacing,
                                0,
                            ),
                        ),
                        rotations,
                    ),
                    UnitChoice(
                        max(
                            first.footprint_width,
                            second.footprint_width,
                        ),
                        first.footprint_height
                        + spacing
                        + second.footprint_height,
                        (
                            UnitMember(first, 0, 0),
                            UnitMember(
                                second,
                                0,
                                first.footprint_height + spacing,
                            ),
                        ),
                        rotations,
                    ),
                )
            )
    return choices
