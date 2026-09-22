"""Non-blocking source QR exceptions, kept separate from fatal cutting violations."""
from automatic_print.layout_engine.cutting.geometry.cut_guide_geometry import detect_guide_band


def collect_image_anomalies(paths, settings, planned=()):
    want_number = bool(settings.number_images)
    want_platform = bool(settings.platform_name and not settings.platform_reuse_qr)
    if not want_number and not want_platform:
        return []
    placements = {str(path): placement for path, placement in planned}
    rows = []
    for path in paths:
        if detect_guide_band(path) is None:
            rows.append({
                'source': path.name,
                'path': str(path),
                'kind': '未找到可靠膜标签区域',
                'action': '原图保留；跳过本张新增文字；刀码及其他图片继续完成排版',
            })
            continue
        placement = placements.get(str(path))
        if placement is None:
            continue
        number_skipped = want_number and not placement.number_width_px
        platform_skipped = want_platform and not placement.platform_width_px
        if not number_skipped and not platform_skipped:
            continue
        if number_skipped and settings.platform_reuse_qr and settings.platform_name:
            kind = '膜标签短边没有经过像素验证的批次及平台尺码文字空位'
            action = '原图保留；跳过本张新增文字；刀码及其他图片继续完成排版'
        elif number_skipped and platform_skipped:
            kind = '膜标签没有经过像素验证的批次及平台文字空位'
            action = '原图保留；跳过本张批次及平台尺码文字；刀码及其他图片继续完成排版'
        elif number_skipped:
            kind = '膜标签没有经过像素验证的批次文字空位'
            action = '原图保留；仅跳过本张批次文字；刀码及其他图片继续完成排版'
        else:
            kind = '膜标签没有经过像素验证的平台文字空位'
            action = '原图保留；仅跳过本张平台尺码文字；刀码及其他图片继续完成排版'
        rows.append({
            'source': path.name,
            'path': str(path),
            'kind': kind,
            'action': action,
        })
    return rows


def anomaly_text(analysis):
    rows = analysis.get('image_anomalies', [])
    if not rows:
        return ''
    return (f'图片异常 {len(rows)} 张（不阻塞生成，原图均保留，请人工核对标记）：\n'
            +'\n'.join(f"{row['source']}：{row['kind']} · {row['action']}" for row in rows))
