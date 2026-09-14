"""Never expose an encoder's partially written file as a printable PNG."""
from .save_progress import monitor_save
from time import perf_counter


def save_png(canvas, target, settings, use_vips, progress):
    pending = target.with_name(target.name+'.未完成')
    details = None
    reason = ''
    save_stage = ['正在编码或写入']
    def report(stage, current, total, name):
        if name != pending.name and current == 0:
            save_stage[0] = name.split(' · ')[0]
        if progress:
            progress(stage, current, total,
                save_stage[0]+' · '+name if name == pending.name else name)
    callback = report if progress else None
    try:
        with monitor_save(pending, callback):
            if getattr(settings, 'png_fast_encoding', False):
                from .png_codecs import fast
                width, height = (canvas.width, canvas.height) if use_vips else canvas.size
                if fast.deflate_encode is None:
                    reason = '快速编码依赖不可用，使用原保存方式'
                elif not settings.save_memory_unlimited and width*height*16 > settings.save_memory_mb*1024*1024:
                    reason = '快速编码缓冲超出已设置内存预算，使用流式/兼容方式'
                else:
                    try:
                        details = fast.save(canvas, pending, settings, use_vips, callback)
                    except (fast.FastEncodingError, MemoryError) as error:
                        reason = '快速编码未完成，使用兼容方式：'+str(error)
                if reason and progress:
                    report('保存图片', 0, 0, reason)
            if details is None:
                start = perf_counter()
                if use_vips:
                    canvas.pngsave(str(pending), compression=settings.png_compression_level, interlace=False)
                else:
                    canvas.save(pending, format='PNG', dpi=(settings.dpi, settings.dpi),
                                compress_level=settings.png_compression_level)
                details = {'encoder': '大图兼容PNG' if use_vips else '标准兼容PNG',
                    'steps': [{'name': '兼容编码与写入（含可能的延迟合成）', 'seconds': perf_counter()-start}]}
            if reason:
                details['fallback_reason'] = reason
    finally:
        if not use_vips:
            canvas.close()
    # Validation follows publication of a fully encoded image; the enclosing
    # production batch remains explicitly marked unfinished until all checks pass.
    pending.rename(target)
    return details
