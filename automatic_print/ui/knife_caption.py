"""Display actual zone knife coordinates, including single-row zones."""
from math import isfinite


def knife_caption(planned, dpi, separator=' · '):
    zones = {p.cut_zone: p.cut_knife_x_px for _, p in planned if p.cut_zone}
    captions = []
    for name, knife in zones.items():
        if knife is None:
            captions.append(f'{name}：单排，无第二刀位')
        elif isinstance(knife, (int, float)) and isfinite(knife):
            captions.append(f'{name}刀位 {knife*25.4/dpi:.1f} 毫米')
        else:
            captions.append(f'{name}：刀位数据异常')
    return separator.join(captions)
