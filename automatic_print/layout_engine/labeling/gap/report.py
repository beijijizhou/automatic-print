"""Gap-record verification and production diagnostics."""
from pathlib import Path


def verify_records(records):
    for record in records:
        expected = record.get('source_identity')
        if expected:
            original = Path(expected[0])
            stat = original.stat()
            if [str(original.resolve()), stat.st_mtime_ns, stat.st_size] != expected:
                raise ValueError(f'{original.name}：补足间距后源文件发生变化，请重新生成')


def annotate_analysis(data, records, settings=None, progress=None):
    data['header_gap'] = records
    if settings and settings.developer_gap_loss and 'height_m' in data:
        from automatic_print.layout_engine.planning.zones.gap_loss import compare_gap_loss
        if progress:
            progress('间距额外用膜比较', 0, 1, '原间距参考，仅几何计算，不生成图片')
        data['gap_loss'] = compare_gap_loss(records, settings, data['height_m'], progress)
        if progress:
            progress('间距额外用膜比较', 1, 1, '原间距参考计算完成')
    rows = data.setdefault('image_anomalies', [])
    if settings and settings.output_dpi_notice:
        data['output_dpi_notice'] = settings.output_dpi_notice
        if not any(row.get('kind') == settings.output_dpi_notice for row in rows):
            rows.append({'source': '整批输出DPI', 'path': '',
                         'kind': settings.output_dpi_notice, 'action': '已自动继续，可手动修改输出DPI'})
    existing = {(row['source'], row['kind']) for row in rows}
    for record in records:
        warning = record['warning']
        if warning and (record['filename'], warning) not in existing:
            rows.append({'source': record['filename'], 'path': record['source'],
                         'kind': warning, 'action': '保留原图间距；请人工核对'})
    return data
