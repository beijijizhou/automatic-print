from pathlib import Path
from automatic_print.layout_engine.output.output_file_info import file_information_text, result_file_report


def record(name='批次.png', size=600_000_000):
    return dict(filename=name, file_size_bytes=size, width_px=6850, height_px=242714,
        output_dpi=300, output_format='PNG', pixel_format='RGBA', bits_per_channel=8,
        alpha_channel=True, png_compression_level=1, png_engine='libvips',
        worker_threads=4,
        timings_seconds={'saving_png': 48.627}, png_save_details={
            'encoder': '原生分块流式PNG',
            'timing_note': '流水线交错执行', 'observed_bytes': size,
            'steps': [
                {'name': '启动至首批PNG数据', 'seconds': 2.0},
                {'name': 'PNG持续生成、压缩与写入', 'seconds': 45.0},
                {'name': '编码收尾与文件刷新', 'seconds': 1.627}]})


def test_file_information_uses_metadata_without_any_file_access(monkeypatch):
    def forbidden(*a, **k):
        raise AssertionError('output diagnostics must not read images or files')
    monkeypatch.setattr(Path, 'open', forbidden)
    monkeypatch.setattr(Path, 'stat', forbidden)
    text = file_information_text(record())
    for expected in ['600.00 MB', '572.20 MiB', '600000000 字节', '6850 × 242714',
                     '水平 300 DPI', '垂直 300 DPI', 'PNG · RGBA · 每通道 8 位',
                     '透明通道：保留', '压缩等级：1', '无损', '原生分块流式PNG', '48.627 秒']:
        assert expected in text
    assert '本批次有效并行：4 线程' in text
    assert '计时口径：流水线交错执行' in text
    assert '保存阶段平均文件产出' in text


def test_segment_report_lists_each_file_size_and_saving_details():
    text = result_file_report({'parts': [record('第一段.png',100_000_000),
                                        record('第二段.png',40_000_000)]})
    assert '合计 140.00 MB' in text
    assert text.count('文件名：') == 2
    assert '第一段.png' in text and '第二段.png' in text
    assert text.count('保存阶段耗时：') == 2
    assert '不相加' in text


def test_preview_does_not_claim_a_saved_file():
    assert result_file_report({'preview_only': True}) == ''


def test_old_records_do_not_invent_pixel_format():
    text = file_information_text({'filename':'旧输出.png'})
    assert 'RGBA' not in text and '透明通道：保留' not in text
