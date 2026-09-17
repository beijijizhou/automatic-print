"""Non-blocking source QR exceptions, kept separate from fatal cutting violations."""
from automatic_print.layout_engine.cutting.geometry.cut_guide_geometry import detect_guide_band


def collect_image_anomalies(paths, settings, planned=()):
    if not settings.platform_name or not settings.number_images:
        return []
    placements = {str(path): placement for path, placement in planned}
    rows = []
    for path in paths:
        if detect_guide_band(path) is None:
            rows.append({
                'source': path.name,
                'path': str(path),
                'kind': '未找到可靠膜标签区域',
                'action': '原图保留；不添加平台文字及标签辅助线；继续完成排版',
            })
            continue
        placement = placements.get(str(path))
        if (settings.platform_reuse_qr and placement is not None
                and not placement.platform_width_px):
            rows.append({
                'source': path.name,
                'path': str(path),
                'kind': '二维码卡片内没有经过像素验证的平台文字空位',
                'action': '原图保留；仅跳过本张平台尺码文字；继续完成排版',
            })
    return rows


def anomaly_text(analysis):
    rows = analysis.get('image_anomalies', [])
    if not rows:
        return ''
    return (f'图片异常 {len(rows)} 张（不阻塞生成，原图均保留，请人工核对标记）：\n'
            +'\n'.join(f"{row['source']}：{row['kind']} · {row['action']}" for row in rows))
