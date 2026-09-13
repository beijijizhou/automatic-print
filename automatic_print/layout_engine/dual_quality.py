"""Expose real paired rows and external marking costs, without weakening safety."""
from collections import defaultdict
from dataclasses import asdict


def dual_quality(planned, settings):
    if settings.cutter_mode != 'dual':
        return {}
    rows = defaultdict(list)
    for _, placement in planned:
        p = asdict(placement)
        rows[(p['cut_zone'], p['y_px'])].append(p)
    paired, singles, rotated = 0, [], 0
    for (zone, _), members in rows.items():
        if zone == '旋转区' or any(p['rotation_degrees'] for p in members):
            rotated += len(members)
        elif len(members) == 2:
            paired += 1
        else:
            for p in members:
                external = bool(p['platform_width_px'] and
                    (p['platform_x_px'] < p['x_px'] or
                     p['platform_x_px']+p['platform_width_px'] > p['x_px']+p['width_px']))
                singles.append({'source': p['source'], 'width_mm': round(p['width_px']*25.4/settings.dpi, 1),
                    'platform_external': external,
                    'reason': '平台文字外置占位，需核对' if external else
                    '需核对图片尺寸、整批刀位及订单/尺码边界'})
    text = f'双排 {paired} 行 · 常规单排 {len(singles)} 张 · 旋转单排 {rotated} 张'
    if singles:
        text += ' · 未达到全双排预期，请核对单排明细；不通过缩图或跨刀位强行双排'
    return {'paired_rows': paired, 'single_images': singles,
            'rotated_images': rotated, 'needs_review': bool(singles), 'text': text}
