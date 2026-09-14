"""Discardable batch-end information, never drawn on production artwork."""
from functools import lru_cache
from PIL import Image
from .labels import label_badge, format_label
from .output_name import order_quantity
from .output_sizes import size_range_label


def footer_text(planned, settings, notice):
    from datetime import datetime
    folders = list(dict.fromkeys(path.parent.name for path, _ in planned))
    paths = [path for path, _ in planned]
    label = format_label(settings.label_text_template, 1, paths[0],
                         datetime.now().astimezone(), settings.label_date_format, settings.machine_number)
    scope = '本段' if settings.batch_footer_context else '批次'
    lines = [f"{notice} · {'+'.join(folders)} · {order_quantity(paths, scope)} · {len(paths)}张",
             f"平台：{settings.platform_name or '未设置'} · 机器：{settings.machine_number} · 标签：{label}"]
    zones = {}
    for path, p in planned:
        zones.setdefault(p.cut_zone or '常规区', []).append((path, p))
    for name, members in zones.items():
        rows = {}
        for _, p in members:
            rows.setdefault(p.row_y_px, []).append(p)
        pairs = sum(len(row) == 2 for row in rows.values())
        knife = members[0][1].cut_knife_x_px
        knife_mm = knife*25.4/settings.dpi if knife is not None else settings.cutter_knife_mm
        sizes = size_range_label([path for path, _ in members]) or '尺码待核对'
        title = '旋转区' if name == '旋转区' else '双排区/常规区'
        length = (max(p.row_y_px+p.footprint_height_px for _, p in members)-
                  min(p.row_y_px for _, p in members))*25.4/settings.dpi/1000
        cut = f'刀位{knife_mm:.1f}毫米' if settings.cutter_mode == 'dual' else '单列/自由排版'
        lines.append(f'{title}：{len(members)}张 · {pairs}行双排 · {sizes} · {length:.3f}米 · {cut}')
    return '\n'.join(lines)+('\n'+settings.batch_footer_context if settings.batch_footer_context else '')


@lru_cache(maxsize=8)
def _pixels(text, dpi, font_mm, width):
    badge = label_badge(text, dpi, font_mm, width)
    try:
        return badge.size, badge.tobytes()
    finally:
        badge.close()


def footer_sprite(rect):
    size, pixels = _pixels(rect['text'], rect['dpi'], rect['font_mm'], rect['max_width'])
    return Image.frombytes('RGBA', size, pixels)


def footer_rect(planned, settings, width, top, notice):
    text = footer_text(planned, settings, notice)
    size, _ = _pixels(text, settings.dpi, settings.batch_footer_font_mm, width)
    return {'x': 0, 'y': top, 'width': size[0], 'height': size[1],
            'kind': '批次信息', 'text': text, 'dpi': settings.dpi,
            'font_mm': settings.batch_footer_font_mm, 'max_width': width}
