"""One linear whole-batch candidate, independent of tail pruning."""
from dataclasses import replace
from .models import mm_to_px
from .transition_marks import marked_height
from .order_validation import validate_order_placements
from .cut_validation import validate_cut_corridor
from .marker_space import validate_embedded_marks


def recover_normal_width(paths,settings,progress,error):
    from .gap_fallback import width_failure
    if settings.cutter_mode not in {'free','single','dual'} or not width_failure(error):
        raise error
    from .order_groups import ordered_paths
    from .rotation_zones import rotation_items, _rotated
    from .images import print_dimensions
    paths=ordered_paths(paths)
    missing_dpi=[p.name for p in paths if not print_dimensions(p,settings.dpi).embedded_dpi]
    if missing_dpi:
        raise ValueError(f'{error}\n无法可靠旋转恢复：以下原图缺内嵌DPI：'+'、'.join(missing_dpi)) from error
    if progress:
        progress('超宽旋转恢复',0,len(paths),'常规方案不可用，尝试整批旋转单排；不缩小原图')
    items,labels=rotation_items(paths,settings,progress)
    missing=[p.name for p in paths if p not in items]
    if missing:
        raise ValueError(f'{error}\n已尝试旋转单排，以下图片旋转后仍无安全占位或膜标签数据：'+
                         '、'.join(missing)+'；未缩小原图。') from error
    rotated=_rotated(paths,settings,(items,labels))
    dual=settings.cutter_mode=='dual'
    planned=[(path,replace(p,cut_zone='旋转区' if dual else '单排区',
                          cut_knife_x_px=p.cut_knife_x_px if dual else None,
                          cut_knife_xs_px=p.cut_knife_xs_px if dual else (),
                          cut_column_count=p.cut_column_count if dual else 1))
             for path,p in rotated[0]]
    maximum=mm_to_px(settings.media_width_mm,settings.dpi)
    from .cutter_planner import cutter_output_width
    width=cutter_output_width(planned,settings,maximum)
    validate_order_placements(paths,planned)
    validate_cut_corridor(planned,settings,width)
    validate_embedded_marks(planned,settings)
    if progress:
        if dual:
            progress('批次刀位已确定',rotated[3],settings.dpi,'原尺寸旋转单排；整批统一刀位，订单与双面相邻')
        progress('超宽旋转恢复',len(paths),len(paths),'已采用旋转单排，不缩小；常规方案无解，不计算虚假省膜基准')
    return planned,labels,width,rotated[2],rotated[2]


def compare_whole(paths, settings, progress, selected, prepared=None):
    if not settings.cutter_compare_whole_rotation or any(degrees % 360 for _,degrees in settings.manual_rotations):
        return selected
    from .rotation_zones import rotation_items, _rotated
    paths = [path for path, _ in selected[0]]
    if progress:
        progress('比较整批旋转', 0, len(paths), '不受双排保护或大尺码尾部筛选限制')
    items, labels = prepared if prepared is not None else rotation_items(paths, settings, progress)
    if len(items) != len(paths):
        if progress:
            progress('比较整批旋转',len(paths),len(paths),f'{len(paths)-len(items)}张无法安全旋转，保留当前方案')
        return selected
    rotated = _rotated(paths, settings, (items, labels))
    planned = [(path, replace(p, cut_zone='旋转区' if settings.cutter_mode == 'dual' else '单排区',
                             cut_knife_x_px=p.cut_knife_x_px if settings.cutter_mode == 'dual' else None,
                             cut_knife_xs_px=p.cut_knife_xs_px if settings.cutter_mode == 'dual' else (),
                             cut_column_count=p.cut_column_count if settings.cutter_mode == 'dual' else 1))
               for path, p in rotated[0]]
    maximum = mm_to_px(settings.media_width_mm, settings.dpi)
    from .cutter_planner import cutter_output_width
    width = cutter_output_width(planned, settings, maximum)
    try:
        validate_order_placements(paths, planned)
        validate_cut_corridor(planned, settings, width)
        validate_embedded_marks(planned, settings)
    except ValueError as error:
        if progress:
            progress('比较整批旋转', len(paths),len(paths),'整批旋转不可用：'+str(error))
        return selected
    height = marked_height(planned, settings,width,rotated[2])
    old = marked_height(selected[0],settings,width,selected[3])
    if progress:
        progress('比较整批旋转',len(paths),len(paths),
                 f'整批旋转 {height*25.4/settings.dpi/1000:.3f}米 · 当前方案 {old*25.4/settings.dpi/1000:.3f}米')
    if height >= old:
        return selected
    if progress:
        progress('批次刀位已确定',rotated[3],settings.dpi,'整批旋转更省膜；完整订单、双面及尺码顺序保留')
    return planned,labels,width,rotated[2],selected[4]
