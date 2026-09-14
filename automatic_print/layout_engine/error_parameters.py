"""Explain actual geometry at failure points without decoding image pixels."""
from PIL import Image
from .images import print_dimensions
from .models import mm_to_px


def limits_text(settings, actual=True):
    full=settings.media_width_mm+settings.riin_left_mm+settings.riin_right_mm
    return (f"{'失败点实际限制参数' if actual else '请求参数（实际输出网格见失败点）'}：\n"
        f"膜宽 {full:g} 毫米 · RIIN左/右预留 {settings.riin_left_mm:g}/{settings.riin_right_mm:g} 毫米"
        f" · 可打印宽度 {settings.media_width_mm:g} 毫米\n"
        f"排版模式 {dict(free='自由排版',single='单排切膜',dual='双排切膜').get(settings.cutter_mode,settings.cutter_mode)}"
        f" · {'实际输出' if actual else '配置'}DPI {settings.dpi:g}"
        f" · 自动刀位 {'开' if settings.cutter_auto_knife else '关'}"
        f" · {'参考刀位（自动无解时不是最终值）' if settings.cutter_auto_knife else '固定刀位'} {settings.cutter_knife_mm:g} 毫米 · 刀位两侧安全距离 {settings.cutter_safety_mm:g} 毫米\n"
        f"允许自动旋转 {'是' if settings.allow_rotation else '否'} · 垂直间距 {settings.spacing_mm:g} 毫米"
        f" · 膜标签补足间距 {settings.membrane_gap_mm:g} 毫米\n"
        f"刀码 {settings.color_block_width_mm:g}×{settings.color_block_height_mm:g} 毫米"
        f" · 刀码间隔 {settings.color_block_gap_mm:g} 毫米"
        f" · 平台字号高度 {settings.platform_font_height_mm:g} 毫米"
        f" · 普通字号 {settings.number_font_size_mm:g} 毫米")


def source_parameters(path, fallback_dpi):
    try:
        dimensions=print_dimensions(path,fallback_dpi)
        with Image.open(path) as image:
            pixels=f'{image.width}×{image.height} 像素 · 格式 {image.format} / {image.mode}'
        if not dimensions.embedded_dpi:
            return pixels+' · 缺可靠内嵌DPI，打印毫米尺寸无法确认'
        return (f'{pixels} · 原DPI {dimensions.x_dpi:.3f}/{dimensions.y_dpi:.3f}'
            f' · 原画布打印尺寸 {dimensions.width_mm:.2f}×{dimensions.height_mm:.2f} 毫米（含透明区）')
    except (OSError,ValueError) as error:
        return '图片参数无法读取：'+str(error)


def item_text(item,settings):
    factor=25.4/settings.dpi
    return (f'{item.path.name}：方向 {item.rotation_degrees}°'
        f' · 图像 {item.width*factor:.2f}×{item.height*factor:.2f} 毫米'
        f' · 含全部标记占位 {item.footprint_width*factor:.2f}×{item.footprint_height*factor:.2f} 毫米'
        f' · 文字宽 {item.label_width*factor:.2f} 毫米 · 平台文字宽 {item.platform_width*factor:.2f} 毫米')


def choices_failure(choices,settings,available_px):
    factor=25.4/settings.dpi
    lines=[limits_text(settings)]
    for i,choice in enumerate(choices,1):
        lines.append(f'候选{i}：需要宽度 {choice.width*factor:.2f} 毫米，允许 {available_px*factor:.2f} 毫米，'
                     f'超出 {max(0,choice.width-available_px)*factor:.2f} 毫米')
        lines.extend(item_text(m.item,settings) for m in choice.members)
    return '\n'.join(lines)


def groups_failure(groups,settings):
    from .left_marker import external_left_item
    lines=[limits_text(settings)]
    if settings.cutter_mode=='dual':
        left=settings.cutter_knife_mm-settings.cutter_safety_mm
        right=settings.media_width_mm-settings.cutter_knife_mm-settings.cutter_safety_mm
        lines.append(f'当前参考分区宽度：左 {left:.2f} 毫米 / 右 {right:.2f} 毫米（未扣右刀码偏移）；自动无解不是某一张必然超宽。')
    for group in groups:
        for item in group:
            item=external_left_item(item)
            needed=item.footprint_width*25.4/settings.dpi
            allowed=mm_to_px(settings.media_width_mm,settings.dpi)*25.4/settings.dpi
            lines.append(item_text(item,settings)+
                f' · 相对全幅：需要 {needed:.2f} / 允许 {allowed:.2f} / 超出 {max(0,needed-allowed):.2f} 毫米')
    return '\n'.join(lines)
