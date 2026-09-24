"""Recover oversized images: force short-side orientation, then scale copies."""
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from time import time
from uuid import uuid4
from PIL import Image
from automatic_print.layout_engine.intake.metadata.images import print_dimensions
from automatic_print.layout_engine.intake.preparation.item_factory import read_items
from automatic_print.layout_engine.labeling.markers.left_marker import external_left_item
from automatic_print.layout_engine.domain.models import mm_to_px
from automatic_print.layout_engine.orders.order_groups import pair_identity


def cache_root():
    from automatic_print.history.store import log_folder
    return log_folder()/'超宽等比缩小副本'


def scaled_copy(path, factor):
    stat=path.stat()
    key=sha256(repr((str(path.resolve()),stat.st_mtime_ns,stat.st_size,factor,'v1')).encode()).hexdigest()
    target=cache_root()/key[:24]/path.name
    if target.is_file() and time()-target.stat().st_mtime<86400:
        return target
    target.parent.mkdir(parents=True,exist_ok=True)
    temporary=target.with_name(target.name+'.'+uuid4().hex[:8]+'.未完成')
    try:
        with Image.open(path) as source:
            dpi=source.info.get('dpi')
            icc=source.info.get('icc_profile')
            with source.convert('RGBA') as rgba:
                size=(max(1,int(rgba.width*factor)),max(1,int(rgba.height*factor)))
                with rgba.resize(size,Image.Resampling.LANCZOS) as smaller:
                    smaller.save(temporary,format='PNG',dpi=dpi,icc_profile=icc,compress_level=1)
        if (path.stat().st_mtime_ns,path.stat().st_size)!=(stat.st_mtime_ns,stat.st_size):
            raise ValueError(f'{path.name}：缩小期间原文件变化，请重新处理')
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def fit_oversized(paths,settings,progress=None):
    if settings.cutter_mode not in {'single', 'dual'}:
        raise ValueError('自动超宽旋转与等比缩小只用于单排或双排后的剩余旋转区')
    settings=replace(settings,sequence_numbers=settings.sequence_numbers or
                     tuple((str(p.resolve()),i) for i,p in enumerate(paths,1)))
    output=list(paths)
    rotations=dict(settings.manual_rotations)
    numbers=dict(settings.sequence_numbers)
    notices=list(settings.width_adjustments)
    width=mm_to_px(settings.media_width_mm,settings.dpi)
    if settings.cutter_mode == 'dual':
        width -= 2*mm_to_px(settings.cutter_safety_mm, settings.dpi)+1
    if width<=0:
        raise ValueError('当前刀位安全分区无可用宽度，无法通过缩小图片恢复')
    def measure(path,degree):
        trial=replace(settings,allow_rotation=False,manual_rotations=((str(path.resolve()),degree),),
                      sequence_numbers=tuple(numbers.items()))
        item=read_items([path],trial,None)[0][0][0]
        return external_left_item(item) if settings.cutter_mode!='free' else item
    for index,path in enumerate(paths):
        if progress:
            progress('超宽自动恢复',index,len(paths),path.name)
        dimensions=print_dimensions(path,settings.dpi)
        current=measure(path,rotations.get(str(path.resolve()),0))
        if settings.cutter_mode == 'single' and current.footprint_width<=width:
            continue
        if not dimensions.embedded_dpi:
            raise ValueError(f'{path.name}：缺可靠DPI，不能自动缩小打印尺寸')
        # This is the deliberately aggressive rotation path. Keep every
        # recovered image horizontal in the rotation zone, then scale the
        # rotated result to the dynamically measured safe width when needed.
        degree=90 if settings.rotation_direction=='left' else 270
        candidate=measure(path,degree)
        if candidate.footprint_width<=width:
            continue
        factor=1.0
        prepared=path
        for attempt in range(4):
            if candidate.footprint_width<=width:
                break
            available=width-(candidate.footprint_width-candidate.width)-1
            if available<=0:
                raise ValueError(f'{path.name}：刀码/文字本身占位已超过膜宽，缩小图案无法恢复')
            factor*=min(.99,available/candidate.width)
            prepared=scaled_copy(path,factor)
            numbers[str(prepared.resolve())]=numbers[str(path.resolve())]
            candidate=measure(prepared,degree)
        if candidate.footprint_width>width:
            raise ValueError(f'{path.name}：自动缩小后标记占位仍超宽，不能安全输出')
        output[index]=prepared
        rotations.pop(str(path.resolve()),None)
        rotations[str(prepared.resolve())]=degree
        final=print_dimensions(prepared,settings.dpi)
        text=(f'超宽自动恢复：强制横向旋转{degree}°，等比比例{factor*100:.2f}%；'
              f'原尺寸{dimensions.width_mm:.2f}×{dimensions.height_mm:.2f}毫米，'
              f'缩后未旋转尺寸{final.width_mm:.2f}×{final.height_mm:.2f}毫米；'
              f'总占位宽{candidate.footprint_width*25.4/settings.dpi:.2f}毫米，'
              f'可打印全幅{settings.media_width_mm:g}毫米，当前安全占位上限{width*25.4/settings.dpi:.2f}毫米。'
              '原图未修改；缩小会改变实际烫印尺寸，请核查。')
        notices.append((path.name,text,str(path)))
        if progress:
            progress('超宽自动恢复',index+1,len(paths),path.name+' · '+text)
    return output,replace(settings,manual_rotations=tuple(rotations.items()),
        sequence_numbers=tuple(numbers.items()),width_adjustments=tuple(notices))


def fit_rotation_overflow(paths, settings, progress=None):
    """Virtually shrink only rotated overflow so order-level comparison can continue."""
    if settings.cutter_mode not in {'single', 'dual'}:
        return settings
    numbers = dict(settings.sequence_numbers) or {
        str(path.resolve()): index for index, path in enumerate(paths, 1)
    }
    rotations = dict(settings.manual_rotations)
    overrides = dict(settings.dimension_overrides)
    notices = list(settings.width_adjustments)
    width = mm_to_px(settings.media_width_mm, settings.dpi)
    if settings.cutter_mode == 'dual':
        width -= 2 * mm_to_px(settings.cutter_safety_mm, settings.dpi) + 1
    degree = 90 if settings.rotation_direction == 'left' else 270
    required_factors = {}

    def measure(path):
        trial = replace(
            settings, allow_rotation=False,
            manual_rotations=((str(path.resolve()), degree),),
            sequence_numbers=tuple(numbers.items()),
            dimension_overrides=tuple(overrides.items()),
        )
        item = read_items([path], trial, None)[0][0][0]
        return external_left_item(item) if settings.cutter_mode != 'free' else item

    for index, path in enumerate(paths, 1):
        key = str(path.resolve())
        original_override = overrides.get(key)
        candidate = measure(path)
        if candidate.footprint_width <= width:
            continue
        dimensions = print_dimensions(path, settings.dpi)
        if not dimensions.embedded_dpi:
            continue
        factor = 1.0
        for _attempt in range(4):
            available = width - (candidate.footprint_width - candidate.width) - 1
            if available <= 0:
                break
            factor *= min(.99, available / candidate.width)
            overrides[key] = (
                dimensions.width_mm * factor, dimensions.height_mm * factor,
            )
            candidate = measure(path)
            if candidate.footprint_width <= width:
                break
        if candidate.footprint_width > width:
            if original_override is None:
                overrides.pop(key, None)
            else:
                overrides[key] = original_override
            continue
        required_factors[path] = factor

    # Both faces are one production unit. If one face needs shrinking, apply
    # the same ratio and direction to its mate so front/back registration and
    # physical size remain identical.
    for source, factor in tuple(required_factors.items()):
        identity = pair_identity(source)
        if not identity:
            continue
        for mate in paths:
            mate_identity = pair_identity(mate)
            if mate_identity and mate_identity[0] == identity[0]:
                required_factors[mate] = min(required_factors.get(mate, 1.0), factor)

    for index, (path, factor) in enumerate(required_factors.items(), 1):
        dimensions = print_dimensions(path, settings.dpi)
        key = str(path.resolve())
        overrides[key] = (
            dimensions.width_mm * factor, dimensions.height_mm * factor,
        )
        rotations[key] = degree
        text = (f'贪心旋转候选：横向旋转{degree}°后等比缩小至 '
                f'{factor*100:.2f}%，使图片、标签和刀码安全占位不超过 '
                f'{width*25.4/settings.dpi:.2f} 毫米；双面采用同一比例，原图不修改。')
        notices.append((path.name, text, str(path)))
        if progress:
            progress('贪心旋转候选', index, len(required_factors), path.name + ' · ' + text)
    return replace(
        settings, manual_rotations=tuple(rotations.items()),
        sequence_numbers=tuple(numbers.items()),
        dimension_overrides=tuple(overrides.items()),
        width_adjustments=tuple(notices),
    )
