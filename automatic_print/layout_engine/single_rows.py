"""Single-column layout: no second knife, two orientations per complete order."""
from dataclasses import replace
from .models import mm_to_px
from .images import print_dimensions
from .item_factory import read_items
from .left_marker import external_left_item, head_margin
from .order_groups import complete_orders, ordered_paths
from .size_policy import ordered_single_blocks
from .units import UnitChoice, UnitMember


def plan_single_rows(paths, settings, progress):
    from .planner import _place_choice, _used_canvas_width
    if not settings.color_block_enabled:
        raise ValueError('单排切膜必须启用左侧刀码。')
    paths = ordered_paths(paths)
    missing = [p.name for p in paths if not print_dimensions(p,settings.dpi).embedded_dpi]
    if missing:
        raise ValueError('图片缺少可靠DPI，无法确定打印尺寸：'+ '、'.join(missing[:20]))
    width = mm_to_px(settings.media_width_mm,settings.dpi)
    spacing = mm_to_px(settings.spacing_mm,settings.dpi)
    margin = head_margin(settings)
    options, labels = read_items(paths,replace(settings,allow_rotation=True),progress)
    items = {row[0].path:[external_left_item(item) for item in row] for row in options}
    normal_valid = all(row[0].footprint_width <= width for row in items.values())
    groups = ordered_single_blocks(complete_orders(paths))
    planned, y, baseline = [], margin, margin
    for index, group in enumerate(groups,1):
        candidates = []
        for orientation in (0,1):
            row = [items[path][min(orientation,len(items[path])-1)] for path in group]
            # Explicit manual orientation has one choice and is never overridden.
            if all(item.footprint_width <= width for item in row):
                candidates.append((sum(item.footprint_height+spacing for item in row),orientation,row))
        if not candidates:
            from .error_parameters import groups_failure
            details=groups_failure([items[path] for path in group],settings)
            raise ValueError(f'{group[0].name}：旋转与不旋转均超出单排可打印膜宽。\n'+details)
        _,_,chosen = min(candidates,key=lambda c:(c[0],c[1]))
        for path,item in zip(group,chosen):
            choice = UnitChoice(item.footprint_width,item.footprint_height,(UnitMember(item,0,0),),0)
            planned.extend((p,replace(placement,cut_zone='单排区',cut_knife_x_px=None))
                           for p,placement in _place_choice(choice,0,y))
            y += item.footprint_height+spacing
            original = items[path][0]
            baseline += (original.footprint_height if original.footprint_width <= width else item.footprint_height)+spacing
        if progress:
            progress('单排方向比较',index,len(groups),'完整订单相邻；无第二刀位，仅按实际占用长度选择方向')
    height = y-spacing+margin
    return planned,labels,min(width,_used_canvas_width(planned)),height,baseline-spacing+margin if normal_valid else height
