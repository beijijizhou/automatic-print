"""Non-blocking source QR exceptions, kept separate from fatal cutting violations."""
from automatic_print.layout_engine.cutting.geometry.cut_guide_geometry import detect_guide_band


def collect_image_anomalies(paths, settings):
    if not settings.platform_name or not settings.number_images:
        return []
    return [{'source': p.name, 'path': str(p), 'kind': '未找到可靠膜标签区域',
             'action': '原图保留；不添加平台文字及标签辅助线；不参与自动旋转'}
            for p in paths if detect_guide_band(p) is None]


def anomaly_text(analysis):
    rows = analysis.get('image_anomalies', [])
    if not rows:
        return ''
    return (f'图片异常 {len(rows)} 张（不阻塞生成，原图均保留，请人工核对标记）：\n'
            +'\n'.join(f"{row['source']}：{row['kind']} · {row['action']}" for row in rows))
