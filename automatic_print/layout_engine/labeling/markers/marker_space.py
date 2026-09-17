"""Keep cutter marks on lane origins while reusing verified transparent pixels."""
from math import floor, ceil
import sqlite3
from automatic_print.layout_engine.labeling.platform.membrane_region import MembraneRegion
from automatic_print.layout_engine.measurement.measurement_session import (
    SESSION, identity, persistent_cache, source_pixels,
)
from automatic_print.layout_engine.measurement.measurement_timing import measured


@measured('刀码与标签透明矩形检查')
def transparent_rect(path, width, height, degrees, rect):
    x, y, w, h = rect
    if w <= 0 or h <= 0:
        return True
    if x < 0 or y < 0 or x+w > width or y+h > height:
        return False
    region = MembraneRegion(x/width, y/height, (x+w)/width, (y+h)/height)
    region = region.rotated((-degrees+180)%360-180)
    session = SESSION.get()
    key = (identity(path), width, height, degrees, tuple(rect)) if session else None
    if session and key in session.rectangles:
        return session.rectangles[key]
    persistent = persistent_key = None
    if session:
        try:
            from automatic_print.layout_engine.measurement.measurement_cache import (
                transparent_rect_key,
            )
            persistent = persistent_cache()
            persistent_key = transparent_rect_key(*key)
            cached = persistent.load('transparent_rect', persistent_key)
            if cached is not None:
                result = bool(cached['transparent'])
                session.rectangles[key] = result
                return result
        except (OSError, ValueError, TypeError, KeyError, sqlite3.Error):
            persistent = persistent_key = None
    with source_pixels(path) as source:
        if 'A' not in source.getbands():
            return False
        box = (max(0, floor(region.left*source.width)-3),
               max(0, floor(region.top*source.height)-3),
               min(source.width, ceil(region.right*source.width)+3),
               min(source.height, ceil(region.bottom*source.height)+3))
        with source.crop(box) as crop:
            result = crop.getchannel('A').getextrema()[1] == 0
    if session:
        session.rectangles[key] = result
        if persistent is not None and persistent_key is not None:
            try:
                persistent.save(
                    'transparent_rect', persistent_key,
                    {'transparent': result},
                )
            except (OSError, ValueError, TypeError, sqlite3.Error):
                pass
    return result


def can_embed_marker(path, width, height, degrees, block, label, platform):
    bx, by, bw, bh = block
    lx, ly, lw, lh = label
    px, py, pw, ph = platform
    if pw and px < 0:
        return False
    for rect in (block, label):
        x, y, w, h = rect
        if not transparent_rect(path, width, height, degrees, rect):
            return False
        if pw and w and h and x < px+pw and x+w > px and y < py+ph and y+h > py:
            return False
    return bool(bw and bh)


def validate_embedded_marks(planned, settings=None):
    """Recheck every source rectangle independently of the packing decision."""
    for path, p in planned:
        if settings:
            from .marker_stack import validate_stack
            validate_stack(path, p, settings)
        has_added_text = bool(
            (p.number_width_px and p.number_height_px)
            or (p.platform_width_px and p.platform_height_px)
        )
        if settings and settings.preserve_header_gap and has_added_text:
            from automatic_print.layout_engine.cutting.geometry.cut_guide_geometry import detect_guide_band
            header = detect_guide_band(path)
            if not header:
                raise ValueError(
                    f'{path.name}：未能可靠识别膜标签高度范围，禁止输出新增文字。'
                )
            header = header.rotated(p.rotation_degrees)
            header_top = p.y_px+round(header.top*p.height_px)
            header_bottom = p.y_px+round(header.bottom*p.height_px)
            for kind,x,y,w,h in (('标签',p.number_x_px,p.number_y_px,p.number_width_px,p.number_height_px),
                          ('平台',p.platform_x_px,p.platform_y_px,p.platform_width_px,p.platform_height_px)):
                if w and h and not (y >= header_top and y+h <= header_bottom):
                    raise ValueError(
                        f'{path.name}：{kind}文字超出膜标签高度范围，可能进入膜标签与图案之间，禁止输出。'
                    )
                overlaps = w and h and x < p.x_px+p.width_px and x+w > p.x_px and y < p.y_px+p.height_px and y+h > p.y_px
                in_header = y >= header_top and y+h <= header_bottom
                reused = (kind == '平台' and settings.platform_reuse_qr and overlaps
                          and transparent_rect(path, p.width_px, p.height_px,
                                               p.rotation_degrees,
                                               (x-p.x_px,y-p.y_px,w,h)))
                if overlaps and not in_header and not reused:
                    raise ValueError(f'{path.name}：文字进入膜标签与图案之间的禁用区域，禁止输出。')
        if p.rotation_degrees % 360:
            from automatic_print.layout_engine.cutting.geometry.cut_guide_geometry import detect_guide_band
            qr = detect_guide_band(path)
            if qr:
                qr = qr.rotated(p.rotation_degrees)
                from automatic_print.layout_engine.cutting.geometry.rotated_marks import marker_top
                external = settings and settings.cutter_left_marker_external and p.color_block_x_px == 0
                expected = p.y_px-round(settings.cutter_left_marker_lift_mm*settings.dpi/25.4) if external else p.y_px+marker_top(qr,p.height_px)
                if p.color_block_width_px and p.color_block_y_px != expected:
                    raise ValueError(f'{path.name}：旋转刀码未处于安全基准高度，禁止输出。')
                preserve_header = bool(settings and settings.preserve_header_gap)
                outside_label = bool(
                    settings
                    and (preserve_header or settings.platform_below_marker)
                    and p.number_x_px+p.number_width_px <= p.x_px
                )
                if (p.number_width_px and not preserve_header
                        and not outside_label and (
                    p.number_x_px != p.x_px+round(qr.left*p.width_px)
                    or p.number_y_px < p.y_px+ceil(qr.bottom*p.height_px)
                )):
                    raise ValueError(f'{path.name}：旋转文字未放在二维码下方，禁止输出。')
        rectangles = [(p.color_block_x_px, p.color_block_y_px,
                       p.color_block_width_px, p.color_block_height_px),
                      (p.number_x_px, p.number_y_px,
                       p.number_width_px, p.number_height_px),
                      (p.platform_x_px, p.platform_y_px,
                       p.platform_width_px, p.platform_height_px)]
        for x, y, w, h in rectangles:
            if w and h and x < p.x_px+p.width_px and x+w > p.x_px and y < p.y_px+p.height_px and y+h > p.y_px:
                if not transparent_rect(path, p.width_px, p.height_px, p.rotation_degrees,
                                        (x-p.x_px, y-p.y_px, w, h)):
                    raise ValueError(f'{path.name}：内置刀码或文字会覆盖原图，禁止输出。')
