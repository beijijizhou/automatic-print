"""Copyable output diagnostics from existing render metadata, without image reads."""
from .png_codecs.fast import timing_text


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
