"""Resolve one reliable output grid per batch from lightweight source headers."""
from dataclasses import replace
from collections import defaultdict


def resolve_output_dpi(paths, settings, progress=None):
    if not settings.follow_source_dpi:
        return settings
    from automatic_print.layout_engine.measurement.parallel_measurement import (
        preload_dimensions,
    )
    dimensions_by_path = preload_dimensions(
        paths, settings, progress, '读取原图DPI')
    groups = defaultdict(list)
    failures = []
    actual_dpi = {}
    for path, dimensions in zip(paths, dimensions_by_path, strict=True):
        if not dimensions.embedded_dpi:
            failures.append(path.name+'：缺少可靠DPI')
        elif round(dimensions.x_dpi) != round(dimensions.y_dpi):
            failures.append(path.name+f'：水平/垂直DPI不同（{dimensions.x_dpi:.2f}/{dimensions.y_dpi:.2f}）')
        else:
            nominal = round(dimensions.x_dpi)
            groups[nominal].append(path.name)
            actual_dpi.setdefault(nominal, dimensions.x_dpi)
    if not failures and len(groups) > 1:
        dpi = (min(groups)+max(groups))/2
        distribution = '；'.join(f'{value} DPI：{len(names)}张' for value,names in sorted(groups.items()))
        notice = (f'原图DPI混合（{distribution}），已自动采用中间值 {dpi:g} DPI继续排版。'
                  '按各图原DPI保持毫米尺寸并重采样，低DPI图会插值、高DPI图会降采样；'
                  '可在打印参数取消跟随原图DPI并手动指定。')
        if progress:
            progress('读取原图DPI',len(paths),len(paths),notice)
        return replace(settings,dpi=dpi,follow_source_dpi=False,
                       output_dpi_origin='mixed_source',output_dpi_notice=notice)
    if failures or len(groups) != 1:
        messages = failures[:5]
        messages += [f'{dpi} DPI：{len(names)} 张，例如 {names[0]}'
                     for dpi, names in sorted(groups.items())]
        raise ValueError('无法统一跟随原图DPI。\n'+'\n'.join(messages)+
                         '\n请在打印参数 → 输出与并行中取消“跟随原图DPI”，手动指定统一输出DPI。')
    dpi = actual_dpi[next(iter(groups))]
    if dpi <= 0:
        raise ValueError('原图DPI无效，请核对源文件。')
    if progress:
        progress('读取原图DPI', len(paths), len(paths),
                 f'输出跟随原图：{dpi:.2f} DPI，保持实际毫米尺寸，不强制升到300 DPI')
    return replace(settings, dpi=dpi, follow_source_dpi=False, output_dpi_origin='source')
