"""Independent whole-batch validation of the continuous vertical cutting corridor."""
from math import ceil
from dataclasses import replace

from .models import mm_to_px


def validate_cut_corridor(planned, settings, canvas_width, left_marker_px=0):
    if settings.cutter_left_marker_external and settings.cutter_mode in {'single', 'dual'}:
        for path, p in planned:
            if p.color_block_width_px and p.color_block_x_px == 0:
                gap = max(1, mm_to_px(settings.color_block_gap_mm, settings.dpi))
                if p.x_px < p.color_block_width_px+gap:
                    raise ValueError(f'{path.name}：左侧刀码必须位于原图外并保留剪切间隙，禁止输出。')
                lift = mm_to_px(settings.cutter_left_marker_lift_mm, settings.dpi)
                if p.color_block_y_px != p.y_px-lift or p.color_block_y_px < 0:
                    raise ValueError(f'{path.name}：左图刀码抬高位置不正确或超出画布，禁止输出。')
    if settings.cutter_mode == "single":
        if any(p.color_block_width_px and p.color_block_x_px != 0 for _, p in planned):
            raise ValueError("单排色块必须位于输出文件最左边缘，禁止输出。")
    if settings.cutter_mode != "dual":
        return None
    if any(p.cut_knife_x_px is not None for _,p in planned):
        zones = []
        for name in dict.fromkeys(p.cut_zone for _,p in planned):
            members = [(path,p) for path,p in planned if p.cut_zone == name]
            knives = {p.cut_knife_x_px for _,p in members}
            if len(knives) != 1 or None in knives:
                raise ValueError("同一区域的刀位不统一，禁止输出。")
            knife = next(iter(knives))
            if name == "旋转区" and len({p.row_y_px for _,p in members}) != len(members):
                raise ValueError("旋转区必须每一行只有一张图片。")
            checked = validate_cut_corridor([(path,replace(p,cut_zone="",cut_knife_x_px=None)) for path,p in members],
                      replace(settings,cutter_knife_mm=knife*25.4/settings.dpi),canvas_width,
                      0)
            checked.update(name=name,start_y_px=min(p.row_y_px for _,p in members),
                           end_y_px=max(p.row_y_px+p.footprint_height_px for _,p in members))
            zones.append(checked)
        zones.sort(key=lambda z:z["start_y_px"])
        if any(a["end_y_px"] > b["start_y_px"] for a,b in zip(zones,zones[1:])):
            raise ValueError("刀位区域重叠，禁止输出。")
        return {"zones":zones,"checked_images":len(planned),"continuous":len(zones)==1,
                "knife_changes":len(zones)-1}
    knife = mm_to_px(settings.cutter_knife_mm, settings.dpi)
    safety = ceil(settings.cutter_safety_mm * settings.dpi / 25.4)
    left, right = knife-safety, knife+safety
    if not 0 < left < right < canvas_width:
        raise ValueError("整批切割线或安全通道超出输出画布，已停止生成。")
    expected_marker = right+mm_to_px(settings.cutter_marker_offset_mm, settings.dpi)
    left_rows = {(p.row_y_px, p.y_px) for _, p in planned if p.x_px < knife}
    violations = []
    for path, p in planned:
        for title, x, width in (
            ("图片", p.x_px, p.width_px),
            ("标签", p.number_x_px, p.number_width_px),
            ("色块", p.color_block_x_px, p.color_block_width_px),
            ('平台名称', p.platform_x_px, p.platform_width_px),
        ):
            if width and x < right and x+width > left:
                violations.append(f"{path.name}：{title}进入整批切割安全通道")
        if p.color_block_width_px:
            if p.x_px >= knife and (p.row_y_px, p.y_px) not in left_rows:
                violations.append(f"{path.name}：单排色块不在输出文件最左边缘")
            expected = left_marker_px if p.x_px < knife else expected_marker
            if p.color_block_x_px != expected:
                violations.append(f"{path.name}：色块未对齐固定分区左边缘")
    if violations:
        raise ValueError("整批贯穿切割检查失败，禁止输出：\n"+"\n".join(violations[:20]))
    return {"knife_x_px": knife, "safe_left_px": left, "safe_right_px": right,
            "checked_images": len(planned), "continuous": True, "left_marker_x_px": left_marker_px}


def validate_canvas_pixels(canvas, check, progress=None):
    if check is None:
        return
    if "zones" in check:
        for zone in check["zones"]:
            validate_canvas_pixels(canvas,zone,progress)
        check["pixel_verified"] = True
        return
    left, right = check["safe_left_px"], check["safe_right_px"]
    top, bottom = check.get("start_y_px",0),check.get("end_y_px",canvas.height)
    for x in range(left, right, 8):
        # Crop BEFORE extracting alpha: never allocate a full-canvas alpha image.
        stripe = canvas.crop((x, top, min(x+8, right), bottom))
        occupied = stripe.getchannel("A").getbbox() is not None
        stripe.close()
        if occupied:
            raise ValueError("合成图片进入整批切割安全通道，已禁止保存打印文件。")
        if progress:
            progress("核对切割通道", min(x+8, right)-left, right-left, "逐段检查全长透明通道")
    check["pixel_verified"] = True


def validate_vips_output(path, check, progress=None, guide_boxes=(), transition_rectangles=()):
    if check is None:
        return
    if "zones" in check:
        for zone in check["zones"]:
            validate_vips_output(path,zone,progress,guide_boxes,transition_rectangles)
        check["pixel_verified"] = True
        return
    import pyvips
    if progress:
        progress("核对切割通道", 0, 1, "扫描输出 PNG 的全长切割通道")
    image = pyvips.Image.new_from_file(str(path), access="sequential")
    from .printed_guides import vips_corridor_is_clear
    if not vips_corridor_is_clear(image, check, guide_boxes, transition_rectangles):
        path.rename(path.with_suffix(".禁止打印"))
        raise ValueError("最终 PNG 进入切割安全通道，文件已标记为禁止打印。")
    check["pixel_verified"] = True
    if progress:
        progress("核对切割通道", 1, 1, "输出 PNG 全长通道检查通过")
