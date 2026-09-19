from pathlib import Path

from PIL import Image
import pytest

from automatic_print.layout_engine import LayoutSettings, generate_layout
from automatic_print.layout_engine.output.output_name import (
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
    assert first.parent == tmp_path / '排版日志' / '.处理中'
    assert not first.parent.exists()  # Path calculation does not create folders.
    first.mkdir(parents=True)
    second = batch_output_directory(tmp_path, '批次123', 'JOB_20260913_120000')
    assert second.name == first.name + ' (2)'
    assert not second.exists()


def test_different_batches_share_cutting_container(tmp_path):
    first = batch_output_directory(tmp_path, '批次123', 'JOB_1')
    second = batch_output_directory(tmp_path, '批次456', 'JOB_2')
    assert first.parent == second.parent == tmp_path / '排版日志' / '.处理中'
    assert first != second


def test_finished_directory_matches_png_and_preserves_existing_output(tmp_path):
    from automatic_print.layout_engine.output.output_name import finish_output_files
    stage = batch_output_directory(tmp_path, '批次123', 'JOB_1')
    stage.mkdir(parents=True)
    filename = '批次123_批次4单 CY26 M1 M-XL.png'
    Image.new('RGBA',(1,1),'red').save(stage/filename)
    final, mapping = finish_output_files(stage,filename)
    assert final == tmp_path/'切膜机文件'
    assert mapping[filename] == filename
    assert (final/filename).is_file() and not stage.exists()
    stage = batch_output_directory(tmp_path, '批次123', 'JOB_2')
    stage.mkdir(parents=True)
    Image.new('RGBA',(1,1),'blue').save(stage/filename)
    second, mapping = finish_output_files(stage,filename)
    assert second == final and mapping[filename] == filename[:-4]+' (2).png'
    with Image.open(final/filename) as old:
        assert old.getpixel((0,0)) == (255,0,0,255)


def test_segment_files_flatten_and_result_names_follow_collision(tmp_path):
    from automatic_print.layout_engine.output.output_name import (
        finish_output_files, remap_result_files,
    )
    stage = batch_output_directory(tmp_path, '批次123', 'JOB_3')
    stage.mkdir(parents=True)
    names = ['批次123 第001段.png', '批次123 第002段.png']
    for name in names:
        Image.new('RGBA', (1, 1), 'red').save(stage/name)
    print_root = tmp_path/'切膜机文件'
    print_root.mkdir()
    Image.new('RGBA', (1, 1), 'blue').save(print_root/names[0])
    output, mapping = finish_output_files(stage, names)
    result = {'filename': names[0], 'files': names.copy(),
              'parts': [{'filename': name} for name in names],
              'placements': [{'output_filename': names[0]}],
              'transition_marks': [{'filename': names[1]}]}
    remap_result_files(result, mapping)
    assert output == print_root
    assert result['filename'] == '批次123 第001段 (2).png'
    assert all((output/name).is_file() for name in result['files'])
    assert result['parts'][0]['filename'] == result['filename']
    assert result['placements'][0]['output_filename'] == result['filename']
    assert result['transition_marks'][0]['filename'] == names[1]


def test_knife_subfolders_preserve_existing_file_and_relative_names(tmp_path):
    from automatic_print.layout_engine.output.output_name import finish_output_files
    stage = batch_output_directory(tmp_path, '批次123', 'JOB_KNIFE')
    stage.mkdir(parents=True)
    names = ['批次123 常规.png', '批次123 旋转区.png']
    for name in names:
        Image.new('RGBA', (1, 1), 'red').save(stage/name)
    root = tmp_path/'切膜机文件'
    (root/'旋转').mkdir(parents=True)
    Image.new('RGBA', (1, 1), 'blue').save(root/'旋转'/names[1])
    output, mapping = finish_output_files(
        stage, names, {names[0]: '常规', names[1]: '旋转'},
    )
    assert output == root
    assert (root/mapping[names[0]]).is_file()
    assert (root/mapping[names[1]]).is_file()
    assert mapping[names[0]] == str(Path('常规')/names[0])
    assert mapping[names[1]] == str(Path('旋转')/'批次123 旋转区 (2).png')
    with Image.open(root/'旋转'/names[1]) as old:
        assert old.getpixel((0, 0)) == (0, 0, 255, 255)
