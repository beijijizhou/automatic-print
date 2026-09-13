from PIL import Image
import pytest

from automatic_print.layout import LayoutSettings, generate_layout
from automatic_print.layout_engine.output_name import (
    label_output_name, batch_directory_name, batch_output_directory,
)


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
    assert result["filename"] == "CY26 M11.png"
    assert (tmp_path / "out" / result["filename"]).is_file()
    second = generate_layout([path], tmp_path / "out", settings)
    assert second["filename"] == "CY26 M11 (2).png"


def test_batch_name_is_in_directory_and_png(tmp_path):
    assert batch_directory_name('批次123', 'JOB_20260913_120000') == '批次123_JOB_20260913_120000'
    assert label_output_name('CY26 M1', '批次123') == '批次123_CY26 M1.png'
    assert label_output_name('CY26', '批次/123') == '批次 123_CY26.png'
    path = tmp_path / 'source.png'
    Image.new('RGBA', (50, 80), 'blue').save(path, dpi=(100, 100))
    settings = LayoutSettings(number_images=False, color_block_enabled=False,
                              label_text_template='CY26 M1')
    first = generate_layout([path], tmp_path / 'out', settings, batch_name='批次123')
    second = generate_layout([path], tmp_path / 'out', settings, batch_name='批次123')
    assert first['filename'] == '批次123_CY26 M1.png'
    assert second['filename'] == '批次123_CY26 M1 (2).png'


def test_same_second_job_uses_new_directory(tmp_path):
    first = batch_output_directory(tmp_path, '批次123', 'JOB_20260913_120000')
    first.mkdir()
    second = batch_output_directory(tmp_path, '批次123', 'JOB_20260913_120000')
    assert second.name == first.name + ' (2)'
    assert not second.exists()
