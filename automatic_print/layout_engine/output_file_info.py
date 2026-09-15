"""Copyable output diagnostics from existing render metadata, without image reads."""
from .png_codecs.fast import timing_text


def production_summary_text(result):
    """One visible summary sourced only from the completed production result."""
    analysis = result.get('analysis', {})
    quality = result.get('dual_quality', {})
    dpi = result.get('output_dpi') or 1
    length_m = result.get('height_mm', 0) / 1000
    film_mm = result.get('film_width_mm')
    if film_mm is None:
        film_mm = result.get('maximum_width_mm', 0)
    area = length_m * film_mm / 1000
    placements = result.get('placements', ())
    image_area = sum(
        placement.get('width_px', 0) * placement.get('height_px', 0)
        for placement in placements
    ) * (25.4 / dpi / 1000) ** 2
    occupancy = 100 * image_area / area if area else 0
    orders = analysis.get('order_count', '待核对')
    pieces = analysis.get('piece_count', '待核对')
    images = analysis.get('image_count', len(placements))
    doubles = analysis.get('double_pairs', 0)
    parallel = quality.get('parallel_text')
    if not parallel:
        pairs = quality.get('paired_rows', 0)
        parallel = f'双排 {pairs} 行 / {pairs*2} 张' if pairs else '无并排'
    singles = len(quality.get('single_images', ()))
    rotation_zone = quality.get('rotated_images', 0)
    rotations = result.get('rotation_count', 0)
    mode = {'free': '正常排版', 'single': '单排切膜', 'dual': '自动多列切膜'}.get(
        result.get('cutter_mode'), result.get('cutter_mode', '未记录'))
    lines = [
        '本批次实际输出总结',
        f"{analysis.get('batch_type', '批次')} · {orders} 个订单组 · {pieces} 件"
        f" · {images} 张图 · {doubles} 组双面",
        f"生产方案：{film_mm / 10:g} 厘米膜 · {mode}",
        f"排版结果：{parallel}"
        f" · 常规单排 {singles} 张 · 旋转区 {rotation_zone} 张"
        f"（实际旋转 {rotations} 张）",
        f"实际用膜：{length_m:.3f} 米 · {area:.3f} 平方米 · 图片占位 {occupancy:.1f}%",
        f"相对常规基准节省：{result.get('saved_length_m', 0):.3f} 米"
        f"（{result.get('saved_percent', 0):.1f}%）",
        f"输出：{result.get('filename', '未记录')} · {dpi:g} DPI",
    ]
    from .batch_analysis import distribution_text
    lines.insert(2, distribution_text(analysis))
    return '\n'.join(lines)


def file_information_text(result):
    if result.get('preview_only'):
        return ''
    size = result.get('file_size_bytes')
    width, height = result.get('width_px'), result.get('height_px')
    dpi = result.get('output_dpi')
    lines = ['输出文件信息', '文件名：'+str(result.get('filename', '未记录'))]
    if size is not None:
        lines.append(f'文件大小：{size/1_000_000:.2f} MB（{size/1048576:.2f} MiB；{size} 字节）')
    if width is not None and height is not None:
        lines.append(f'像素尺寸：{width} × {height} 像素')
    if dpi is not None:
        lines.append(f'写入打印分辨率：水平 {dpi:g} DPI · 垂直 {dpi:g} DPI')
        origin = result.get('output_dpi_origin')
        lines.append('输出DPI模式：'+({'source':'跟随原图','mixed_source':'混合原图自动中间值'}.get(origin,'手动指定')))
        notice = result.get('analysis', {}).get('output_dpi_notice')
        if notice:
            lines.append(notice)
    if result.get('pixel_format'):
        bits = result.get('bits_per_channel', '未记录')
        lines.append(f"图片格式：{result.get('output_format', '未记录')} · {result['pixel_format']} · 每通道 {bits} 位")
    if 'alpha_channel' in result:
        lines.append('透明通道：'+('保留' if result['alpha_channel'] else '无'))
    level = result.get('png_compression_level')
    if level is not None:
        labels = {0: '不压缩', 1: '轻度压缩', 3: '中度压缩'}
        lines.append(f'压缩等级：{level}（{labels.get(level, "自定义")}；无损）')
    if result.get('png_engine'):
        engine = {'libvips': '原生分块引擎', 'Pillow': '普通兼容引擎'}.get(
            result['png_engine'], result['png_engine'])
        lines.append('实际合成引擎：'+engine)
    seconds = result.get('timings_seconds', {}).get('saving_png')
    if seconds is not None:
        lines.append(f'保存阶段耗时：{seconds:.3f} 秒（可能包含延迟合成、编码与写入）')
    details = timing_text(result.get('png_save_details'))
    if details:
        lines.append(details)
    lines.append('以上信息来自本次生成记录，未重新读取或解压输出大图。')
    return '\n'.join(lines)


def result_file_report(result):
    if result.get('preview_only'):
        return ''
    parts = result.get('parts')
    if not parts:
        return file_information_text(result)
    size = sum(part.get('file_size_bytes', 0) for part in parts)
    lines = [f'分段输出文件信息：{len(parts)} 个文件 · 合计 {size/1_000_000:.2f} MB',
             '各段保存耗时可能并行重叠，不相加作为整批总耗时。']
    lines.extend(file_information_text(part) for part in parts)
    return '\n\n'.join(lines)
