"""Left-lane artwork clearance; right-lane embedding remains unchanged."""
from dataclasses import replace
from functools import lru_cache


@lru_cache(maxsize=4096)
def external_left_item(item):
    gap = item.left_marker_gap_px
    if not gap or not item.block_width:
        return item
    if item.preserve_header_gap:
        block_y = item.image_ry-item.left_marker_lift_px
        return replace(
            item,
            block_ry=block_y,
            footprint_height=max(
                item.footprint_height,
                block_y+item.block_height,
            ),
        )
    dx = max(0, item.block_width+gap-item.image_rx)
    image_x = item.image_rx+dx
    if item.platform_below_marker:
        lift = item.image_ry-item.left_marker_lift_px-item.block_ry
        if item.platform_reuse_qr and item.label_width:
            from automatic_print.layout_engine.cutting.geometry.cut_guide_geometry import detect_guide_band
            band = detect_guide_band(item.path)
            if band is None:
                raise ValueError(f'{item.path.name}：未能可靠识别膜标签高度范围，禁止输出新增文字。')
            band = band.rotated(item.rotation_degrees)
            top, bottom = round(band.top*item.height), round(band.bottom*item.height)
            if item.label_height > bottom-top:
                raise ValueError(f'{item.path.name}：标签文字无法完整放入膜标签高度范围，禁止输出。')
            label_x = item.block_width+gap
            image_x = max(image_x, label_x+item.label_width+gap)
            dx = image_x-item.image_rx
            return replace(item, image_rx=image_x, block_rx=0,
                label_rx=label_x, label_ry=item.image_ry+top,
                platform_rx=item.platform_rx+dx,
                block_ry=item.image_ry-item.left_marker_lift_px,
                footprint_width=max(image_x+item.width, label_x+item.label_width),
                footprint_height=max(item.footprint_height,
                    item.image_ry+top+item.label_height,
                    item.image_ry-item.left_marker_lift_px+item.block_height))
        label_y = item.label_ry+lift
        platform_x = item.platform_rx+dx if item.platform_reuse_qr else 0
        platform_y = item.platform_ry if item.platform_reuse_qr else item.platform_ry+lift
        return replace(item, image_rx=image_x, block_rx=0, label_rx=0, platform_rx=platform_x,
            block_ry=item.image_ry-item.left_marker_lift_px, label_ry=label_y, platform_ry=platform_y,
            footprint_width=max(image_x+item.width, item.block_width, item.label_width,
                                platform_x+item.platform_width),
            footprint_height=max(item.image_ry+item.height, item.image_ry-item.left_marker_lift_px+item.block_height,
                label_y+item.label_height if item.label_width else 0,
                platform_y+item.platform_height if item.platform_width else 0))
    platform_x = item.platform_rx+dx
    # Rotated text follows the membrane card; upright text stays under the mark.
    label_x = item.label_rx+dx if item.rotation_degrees and not item.preserve_header_gap else 0
    width = max(image_x+item.width, item.block_width,
                label_x+item.label_width if item.label_width else 0,
                platform_x+item.platform_width if item.platform_width else 0)
    return replace(item, image_rx=image_x, block_rx=0, label_rx=label_x,
                   block_ry=item.image_ry-item.left_marker_lift_px,
                   label_ry=item.label_ry-item.left_marker_lift_px
                   if not item.rotation_degrees and item.block_ry != item.image_ry-item.left_marker_lift_px
                   else item.label_ry,
                   platform_rx=platform_x, footprint_width=width)


def head_margin(settings):
    from automatic_print.layout_engine.domain.models import mm_to_px
    lift = settings.cutter_left_marker_lift_mm if settings.cutter_left_marker_external else 0
    if lift < 0 or lift > settings.spacing_mm:
        raise ValueError('左图刀码抬高量必须在0与图片垂直间距之间，请调整打印设置。')
    return mm_to_px(max(settings.margin_mm, lift), settings.dpi)
