"""Expose real paired rows and external marking costs, without weakening safety."""
from collections import defaultdict
from dataclasses import asdict


def dual_quality(planned, settings, analysis=None):
    if settings.cutter_mode != 'dual':
        return {}
    rows = defaultdict(list)
    for _, placement in planned:
        p = asdict(placement)
        rows[(p['cut_zone'], p['row_y_px'])].append(p)
    paired, singles, rotated, embedded = 0, [], 0, 0
    reasons = _analysis_reasons(analysis)
    for members in rows.values():
        embedded += sum(bool(p['color_block_width_px'] and p['x_px'] <= p['color_block_x_px']
            and p['color_block_x_px']+p['color_block_width_px'] <= p['x_px']+p['width_px']) for p in members)
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
                    'footprint_mm': round(p['footprint_width_px']*25.4/settings.dpi, 1),
                    'reason': reasons.get(p['source']) or (
                        '平台文字外置占位，增大了并排宽度' if external else
                        '当前相邻订单、尺码及固定刀位条件下没有安全搭档')})
    text = f'双排 {paired} 行 · 常规单排 {len(singles)} 张 · 旋转单排 {rotated} 张'
    text += f' · 刀码内置 {embedded} 张（复用透明空位）'
    if singles:
        text += ' · 未达到全双排预期，请核对单排明细；不通过缩图或跨刀位强行双排'
    return {'paired_rows': paired, 'single_images': singles,
            'rotated_images': rotated, 'embedded_marks': embedded,
            'needs_review': bool(singles), 'text': text}


def _analysis_reasons(analysis):
    result = {}
    for order in (analysis or {}).get('orders', []):
        reason = order.get('reason', '')
        for item in order.get('items', []):
            for image in item.get('images', []):
                result[image.get('name', '')] = reason
    return result
