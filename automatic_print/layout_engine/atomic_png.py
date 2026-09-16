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
        native_pipeline = False
        with monitor_save(pending, callback) as observation:
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
                    canvas.pngsave(str(pending), compression=settings.png_compression_level,
                                   interlace=False, filter='up')
                else:
                    canvas.save(pending, format='PNG', dpi=(settings.dpi, settings.dpi),
                                compress_level=settings.png_compression_level)
                encoder = ('原生分块流式PNG' if getattr(settings, 'png_streaming', False)
                           else '大图兼容PNG') if use_vips else '标准兼容PNG'
                name = ('延迟合成、固定UP滤波、PNG压缩与写入' if use_vips and getattr(settings, 'png_streaming', False)
                        else '兼容编码与写入（含可能的延迟合成）')
                details = {'encoder': encoder,
                    'steps': [{'name': name, 'seconds': perf_counter()-start}]}
                native_pipeline = use_vips and getattr(
                    settings, 'png_streaming', False
                )
            if reason:
                details['fallback_reason'] = reason
    finally:
        if not use_vips:
            canvas.close()
    # Validation follows publication of a fully encoded image; the enclosing
    # production batch remains explicitly marked unfinished until all checks pass.
    if native_pipeline:
        details['steps'] = observation.steps()
        details['timing_note'] = (
            '原生流式引擎会把源图解码、旋转缩放、分块合成、PNG过滤压缩'
            '和磁盘写入交错执行；这里按文件增长边界拆分，不虚构互斥CPU耗时。'
        )
        details['observed_bytes'] = observation.bytes_written
    publish_started = perf_counter()
    pending.rename(target)
    details['production_seconds'] = sum(
        row.get('seconds', 0) for row in details.get('steps', ())
    )
    details.setdefault('steps', []).append({
        'name': '未完成文件原子发布',
        'seconds': perf_counter() - publish_started,
    })
    return details
