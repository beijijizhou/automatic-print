"""Independent whole-batch validation of the continuous vertical cutting corridor."""
from math import ceil
from dataclasses import replace

from automatic_print.layout_engine.domain.models import mm_to_px


def corridor_checks(check):
    """Flatten whole-output, zone and multi-knife checks into physical corridors."""
    if not check:
        return []
    result = []
    for zone in check.get('zones', [check]):
        inherited = {key: zone[key] for key in ('name', 'start_y_px', 'end_y_px')
                     if key in zone}
        for corridor in zone.get('corridors', [zone]):
            if 'safe_left_px' in corridor:
                result.append(corridor | inherited)
    return result


def mark_pixel_verified(check):
    if not check:
        return
    check['pixel_verified'] = True
    for zone in check.get('zones', ()):
        zone['pixel_verified'] = True
        for corridor in zone.get('corridors', ()):
            corridor['pixel_verified'] = True
    for corridor in check.get('corridors', ()):
        corridor['pixel_verified'] = True


def validate_cut_corridor(planned, settings, canvas_width, left_marker_px=0):
    if settings.cutter_left_marker_external and settings.cutter_mode in {'single', 'dual'}:
        for path, p in planned:
            if p.color_block_width_px and p.color_block_x_px == 0:
                if p.x_px < p.color_block_x_px+p.color_block_width_px:
                    raise ValueError(f'{path.name}：左侧刀码必须完整位于原图外，禁止输出。')
                lift = mm_to_px(settings.cutter_left_marker_lift_mm, settings.dpi)
                if p.color_block_y_px != p.y_px-lift or p.color_block_y_px < 0:
                    raise ValueError(f'{path.name}：左图刀码抬高位置不正确或超出画布，禁止输出。')
    if settings.cutter_mode == "single":
        if any(p.color_block_width_px and p.color_block_x_px != 0 for _, p in planned):
            raise ValueError("单排色块必须位于输出文件最左边缘，禁止输出。")
    if settings.cutter_mode != "dual":
        return None
    if planned and all(p.cut_column_count == 1 for _, p in planned):
        return {"knife_xs_px": [], "corridors": [],
                "checked_images": len(planned), "continuous": True,
                "left_marker_x_px": left_marker_px, "column_count": 1}
    if any(p.cut_knife_x_px is not None or p.cut_knife_xs_px for _,p in planned):
        zones = []
        for name in dict.fromkeys(p.cut_zone for _,p in planned):
            members = [(path,p) for path,p in planned if p.cut_zone == name]
            knife_sets = {_placement_knives(p) for _, p in members}
            if len(knife_sets) != 1:
                raise ValueError("同一区域的刀位不统一，禁止输出。")
            knives = next(iter(knife_sets))
            checked = _validate_fixed_knives(members, settings, canvas_width,
                                             knives, 0)
            checked.update(name=name,start_y_px=min(p.row_y_px for _,p in members),
                           end_y_px=max(p.row_y_px+p.footprint_height_px for _,p in members))
            zones.append(checked)
        zones.sort(key=lambda z:z["start_y_px"])
        if any(a["end_y_px"] > b["start_y_px"] for a,b in zip(zones,zones[1:])):
            raise ValueError("刀位区域重叠，禁止输出。")
        return {"zones":zones,"checked_images":len(planned),"continuous":len(zones)==1,
                "knife_changes":len(zones)-1}
    knives = _placement_knives(planned[0][1]) if planned else ()
    if not knives:
        knives = (mm_to_px(settings.cutter_knife_mm, settings.dpi),)
    return _validate_fixed_knives(planned, settings, canvas_width, knives,
                                  left_marker_px)


def _placement_knives(placement):
    if placement.cut_knife_xs_px:
        return tuple(placement.cut_knife_xs_px)
    return ((placement.cut_knife_x_px,)
            if placement.cut_knife_x_px is not None else ())


def _validate_fixed_knives(planned, settings, canvas_width, knives, left_marker_px):
    safety = ceil(settings.cutter_safety_mm * settings.dpi / 25.4)
    corridors = [(knife-safety, knife+safety) for knife in knives]
    if any(not 0 < left <= right < canvas_width for left, right in corridors):
        raise ValueError("整批切割线或安全通道超出输出画布，已停止生成。")
    offset = mm_to_px(settings.cutter_marker_offset_mm, settings.dpi)
    first_rows = {(p.row_y_px, p.y_px) for _, p in planned
                  if not knives or p.x_px < knives[0]}
    violations = []
    for path, p in planned:
        for title, x, width in (
            ("图片", p.x_px, p.width_px),
            ("标签", p.number_x_px, p.number_width_px),
            ("色块", p.color_block_x_px, p.color_block_width_px),
            ('平台名称', p.platform_x_px, p.platform_width_px),
        ):
            for left, right in corridors:
                if width and x < right and x+width > left:
                    violations.append(f"{path.name}：{title}进入整批切割安全通道")
        if p.color_block_width_px:
            lane = sum(p.x_px >= knife for knife in knives)
            if lane and (p.row_y_px, p.y_px) not in first_rows:
                violations.append(f"{path.name}：单排色块不在输出文件最左边缘")
            expected = (left_marker_px if lane == 0 else
                        knives[lane-1] + safety + offset)
            if p.color_block_x_px != expected:
                violations.append(f"{path.name}：色块未对齐固定分区左边缘")
    if violations:
        raise ValueError("整批贯穿切割检查失败，禁止输出：\n"+"\n".join(violations[:20]))
    checks = [{"knife_x_px": knife, "safe_left_px": left,
               "safe_right_px": right} for knife, (left, right)
               in zip(knives, corridors)]
    result = {"knife_xs_px": list(knives), "corridors": checks,
              "checked_images": len(planned), "continuous": True,
              "left_marker_x_px": left_marker_px}
    if len(checks) == 1:
        result.update(checks[0])
    return result


def validate_canvas_pixels(canvas, check, progress=None):
    if check is None:
        return
    for corridor in corridor_checks(check):
        left, right = corridor["safe_left_px"], corridor["safe_right_px"]
        top = corridor.get("start_y_px", 0)
        bottom = corridor.get("end_y_px", canvas.height)
        for x in range(left, right, 8):
            stripe = canvas.crop((x, top, min(x+8, right), bottom))
            occupied = stripe.getchannel("A").getbbox() is not None
            stripe.close()
            if occupied:
                raise ValueError("合成图片进入整批切割安全通道，已禁止保存打印文件。")
            if progress:
                progress("核对切割通道", min(x+8, right)-left, right-left,
                         "逐段检查全长透明通道")
    mark_pixel_verified(check)


def validate_vips_output(path, check, progress=None, guide_boxes=(), transition_rectangles=()):
    if check is None:
        return
    import pyvips
    kind = 'TIFF' if path.suffix.lower() in {'.tif', '.tiff'} else 'PNG'
    if progress:
        progress("核对切割通道", 0, 1, f"扫描输出 {kind} 的全长切割通道")
    corridors = sorted(
        corridor_checks(check), key=lambda row: row.get("start_y_px", 0)
    )
    image = pyvips.Image.new_from_file(
        str(path), access="sequential")
    from automatic_print.layout_engine.cutting.geometry.printed_guides import vips_corridors_are_clear
    if not vips_corridors_are_clear(
        image, corridors, guide_boxes, transition_rectangles
    ):
        path.rename(path.with_suffix(".禁止打印"))
        raise ValueError(f"最终 {kind} 进入切割安全通道，文件已标记为禁止打印。")
    mark_pixel_verified(check)
    if progress:
        progress("核对切割通道", 1, 1, f"输出 {kind} 全长通道检查通过")
