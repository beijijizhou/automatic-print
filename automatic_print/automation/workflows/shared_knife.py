"""Production gate for batches intended to share one unchanged cutter setup."""

from dataclasses import replace
from dataclasses import dataclass

from ...layout_engine.domain.models import LayoutSettings, mm_to_px


def locked_knife_settings(settings: LayoutSettings) -> LayoutSettings:
    """Keep the operator's selected knife, disabling per-batch knife searches."""
    if settings.cutter_mode != 'dual':
        raise ValueError('连续打印需要先选择自动多列切膜模式。')
    if settings.cutter_knife_mm <= 0 or settings.cutter_knife_mm >= settings.media_width_mm:
        raise ValueError('固定中间刀位必须位于当前可打印膜宽内。')
    return replace(
        settings, cutter_auto_knife=False, strict_fixed_knife=True,
        force_small_pair_width=True,
        cutter_rotation_zone=False,
        cutter_majority_two_zone=False, cutter_tail_rotation=False,
        cutter_compare_whole_rotation=False, allow_rotation=False,
        developer_compact_cutter_layout=False,
    )


def actual_knife_signatures(result: dict) -> set[tuple[int, ...]]:
    """Inspect every rendered placement, including every output segment."""
    signatures = set()
    for placement in result.get('placements') or ():
        knives = tuple(placement.get('cut_knife_xs_px') or ())
        if not knives and placement.get('cut_knife_x_px') is not None:
            knives = (placement['cut_knife_x_px'],)
        signatures.add(knives)
    return signatures


def continuous_print_eligibility(result: dict, settings: LayoutSettings) -> tuple[bool, str]:
    """Never send a changed or second-knife layout to unattended printing."""
    if result.get('preview_only') or not result.get('placements'):
        return False, '没有已保存的排版图，不能连续打印'
    if not result.get('order_check'):
        return False, '没有完成整批订单与双面连续性校验'
    if result.get('cutter_mode') != 'dual':
        return False, '不是双列切膜输出'
    expected_film = settings.media_width_mm + settings.riin_left_mm + settings.riin_right_mm
    if abs(float(result.get('film_width_mm') or 0) - expected_film) > .01:
        return False, '实际输出膜宽或RIIN预留与连续打印配置不同'
    dpi = result.get('output_dpi')
    if not isinstance(dpi, (int, float)) or dpi <= 0:
        return False, '最终输出缺少有效DPI，不能确认物理刀位'
    expected = (mm_to_px(settings.cutter_knife_mm, dpi),)
    signatures = actual_knife_signatures(result)
    if signatures != {expected}:
        return False, f'实际纵刀位 {sorted(signatures)} 与锁定刀位 {expected} 不一致'
    corridor = result.get('cut_corridor') or {}
    if not corridor.get('pixel_verified'):
        return False, '没有完成实际输出像素刀位复核'
    return True, f'整批共用固定刀位 {settings.cutter_knife_mm:g} 毫米'


@dataclass(frozen=True)
class BatchRoute:
    batch: str
    output: str
    unattended: bool
    reason: str


def route_finished_batches(records: list[dict], settings: LayoutSettings) -> tuple[BatchRoute, ...]:
    """Route every successful batch by output facts, not by its requested mode."""
    routes = []
    for record in records:
        eligible, reason = continuous_print_eligibility(record['result'], settings)
        routes.append(BatchRoute(str(record['folder']), str(record['output']), eligible, reason))
    return tuple(routes)
