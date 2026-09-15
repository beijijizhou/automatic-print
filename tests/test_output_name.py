from PIL import Image
import pytest

from automatic_print.layout import LayoutSettings, generate_layout
from automatic_print.layout_engine.output_name import (
    label_output_name, batch_directory_name, batch_output_directory, order_quantity,
    production_quantity,
)


def test_order_quantity_deduplicates_prefixes_pieces_and_faces(tmp_path):
    paths = [tmp_path/name for name in (
        'A00001-B1-1-T-Black-M-NO1-1.png',
        'A00002-B1-1-T-Black-M-NO1-2.png',
        'CVC面料00003-B1-2-T-Black-L-NO1-1.png',
        'B2-1-T-Black-M-NO1-1.png')]
    assert order_quantity(paths) == '批次2单'
    assert order_quantity(paths+[tmp_path/'unknown.png']) == '批次已识别2单 订单待核对'
    assert production_quantity(paths) == '批次2单 3件'
    assert production_quantity(paths+[tmp_path/'unknown.png']) == (
        '批次已识别2单 订单待核对 件数待核对'
    )


def test_whole_output_name_includes_order_count_and_source_batch(tmp_path):
    paths = [tmp_path/f'B{i}-1-T-Black-M-NO1-1.png' for i in range(2)]
    for path in paths:
        Image.new('RGBA', (50, 80), 'blue').save(path, dpi=(100, 100))
    result = generate_layout(paths, tmp_path/'out', LayoutSettings(
        number_images=False, color_block_enabled=False, label_text_template='CY26'),
        batch_name='609140634009')
    assert result['filename'] == '609140634009_批次2单 2件 CY26 M.png'


@pytest.mark.parametrize("text, expected", [
    ("CY 1001Mt26", "CY 1001Mt26.png"),
    ("CY\nM1/26", "CY M1 26.png"),
    ("CON", "标签_CON.png"),
    ("", "排版图片.png"),
    ("标签.png", "标签.png"),
])
def test_label_names_are_portable(text, expected):
    assert label_output_name(text) == expected


def test_generation_uses_label_name_without_overwriting_existing_file(tmp_path):
    path = tmp_path / "source.png"
    Image.new("RGBA", (50, 80), "blue").save(path, dpi=(100, 100))
    settings = LayoutSettings(number_images=False, color_block_enabled=False,
                              label_text_template="CY______26 {机器号}", machine_number="M11")
    result = generate_layout([path], tmp_path / "out", settings)
    assert result["filename"] == "批次订单待核对 件数待核对 CY26 M11.png"
    assert (tmp_path / "out" / result["filename"]).is_file()
    second = generate_layout([path], tmp_path / "out", settings)
    assert second["filename"] == "批次订单待核对 件数待核对 CY26 M11 (2).png"


def test_batch_name_is_in_directory_and_png(tmp_path):
    assert batch_directory_name('批次123', 'JOB_20260913_120000') == '批次123'
    assert label_output_name('CY26 M1', '批次123') == '批次123_CY26 M1.png'
    assert label_output_name('CY26', '批次/123') == '批次 123_CY26.png'
    path = tmp_path / 'source.png'
    Image.new('RGBA', (50, 80), 'blue').save(path, dpi=(100, 100))
    settings = LayoutSettings(number_images=False, color_block_enabled=False,
                              label_text_template='CY26 M1')
    first = generate_layout([path], tmp_path / 'out', settings, batch_name='批次123')
    second = generate_layout([path], tmp_path / 'out', settings, batch_name='批次123')
    assert first['filename'] == '批次123_批次订单待核对 件数待核对 CY26 M1.png'
    assert second['filename'] == '批次123_批次订单待核对 件数待核对 CY26 M1 (2).png'


def test_same_second_job_uses_new_directory(tmp_path):
    first = batch_output_directory(tmp_path, '批次123', 'JOB_20260913_120000')
    assert first.parent == tmp_path / '切膜机文件'
    assert not first.parent.exists()  # Path calculation does not create folders.
    first.mkdir(parents=True)
    second = batch_output_directory(tmp_path, '批次123', 'JOB_20260913_120000')
    assert second.name == first.name + ' (2)'
    assert not second.exists()


def test_different_batches_share_cutting_container(tmp_path):
    first = batch_output_directory(tmp_path, '批次123', 'JOB_1')
    second = batch_output_directory(tmp_path, '批次456', 'JOB_2')
    assert first.parent == second.parent == tmp_path / '切膜机文件'
    assert first != second


def test_finished_directory_matches_png_and_preserves_existing_output(tmp_path):
    from automatic_print.layout_engine.output_name import finish_output_directory
    stage = tmp_path/'批次123'
    stage.mkdir()
    filename = '批次123_批次4单 CY26 M1 M-XL.png'
    Image.new('RGBA',(1,1),'red').save(stage/filename)
    final = finish_output_directory(stage,filename)
    assert final.name == filename[:-4]
    assert (final/filename).is_file() and not stage.exists()
    stage.mkdir()
    Image.new('RGBA',(1,1),'blue').save(stage/filename)
    second = finish_output_directory(stage,filename)
    assert second.name == final.name+' (2)'
    with Image.open(final/filename) as old:
        assert old.getpixel((0,0)) == (255,0,0,255)
