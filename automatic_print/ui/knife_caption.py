"""Display actual zone knife coordinates, including single-row zones."""
from math import isfinite


def knife_caption(planned, dpi, separator=' · '):
    zones = {p.cut_zone: (p.cut_knife_xs_px or ((p.cut_knife_x_px,)
             if p.cut_knife_x_px is not None else ()))
             for _, p in planned if p.cut_zone}
    captions = []
    for name, knives in zones.items():
        if not knives:
            captions.append(f'{name}：单排，无内部刀位')
        elif all(isinstance(knife, (int, float)) and isfinite(knife) for knife in knives):
            values = '、'.join(f'{knife*25.4/dpi:.1f}' for knife in knives)
            captions.append(f'{name}刀位 {values} 毫米')
        else:
            captions.append(f'{name}：刀位数据异常')
    return separator.join(captions)
