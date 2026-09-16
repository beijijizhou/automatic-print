from dataclasses import replace

from PIL import Image
import pytest

from automatic_print.layout import LayoutSettings, generate_layout
from automatic_print.layout_engine.cut_guide_geometry import detect_guide_band
from automatic_print.layout_engine.item_factory import read_items
from automatic_print.layout_engine.platform_label import numbered_template, platform_badge
from automatic_print.layout_engine.segmented_output import shift_part
from automatic_print.layout_engine.cut_validation import validate_cut_corridor


def qr_image(path):
    cv2 = pytest.importorskip('cv2')
    qr = cv2.QRCodeEncoder_create().encode('TEST123')
    image = Image.new('RGBA', (180, 250), 'blue')
    image.paste(Image.fromarray(qr).convert('RGBA'), (10, 10))
    image.save(path, dpi=(25.4, 25.4))
    assert detect_guide_band(path) is not None
    return path


def settings(**values):
    return LayoutSettings(**(dict(dpi=25.4, margin_mm=0, cutter_mode='dual',
        platform_name='隆丰', label_sequence_enabled=True, label_text_template='CY',
        label_position='block_below', allow_rotation=False) | values))


@pytest.mark.parametrize('engine', ['pillow', 'libvips'])
def test_full_batch_platform_badges_and_numbers_are_printed_safely(tmp_path, engine):
    paths = [qr_image(tmp_path/f'B{i}-1-T-Black-M-NO1-1.png') for i in range(12)]
    payloads = []
    result = generate_layout(paths, tmp_path/'out', settings(png_engine=engine,
        label_machine_enabled=True, machine_number='M11'), plan_ready=payloads.append)
    assert payloads[0]['labels'] == {i: f'CY M11 {i}' for i in range(1, 13)}
    assert result['cut_corridor']['pixel_verified']
    first_path, first = payloads[0]['planned'][0]
    with pytest.raises(ValueError, match='平台名称进入整批切割安全通道'):
        validate_cut_corridor([(first_path, replace(first, platform_x_px=300))], settings(), 600)
    with Image.open(tmp_path/'out'/result['filename']) as output:
        for path, p in payloads[0]['planned']:
            qr = detect_guide_band(path)
            target = round(qr.bottom*p.height_px)-round(qr.top*p.height_px)
            assert p.platform_height_px == target
            assert p.platform_y_px == p.y_px+round(qr.top*p.height_px)
            assert p.platform_x_px+p.platform_width_px < p.x_px
            box = (p.platform_x_px, p.platform_y_px,
                   p.platform_x_px+p.platform_width_px, p.platform_y_px+p.platform_height_px)
            badge = output.crop(box)
            assert badge.getchannel('A').getbbox() is not None
            assert (0, 0, 0, 255) in set(badge.getdata())
            assert p.color_block_x_px in (0, 303)
    shifted, _ = shift_part(payloads[0]['planned'][4:], 0)
    offset = payloads[0]['planned'][4][1].row_y_px
    assert shifted[0][1].platform_y_px == payloads[0]['planned'][4][1].platform_y_px-offset


@pytest.mark.parametrize('degrees', [90, -90, 180])
@pytest.mark.parametrize('engine', ['pillow', 'libvips'])
def test_rotated_platform_uses_actual_rotated_qr_height(tmp_path, degrees, engine):
    path = qr_image(tmp_path/'ORDER-1-T-Black-M-NO1-1.png')
    options, _ = read_items([path], settings(cutter_mode='single',
        manual_rotations=((str(path.resolve()), degrees),)), None)
    item = options[0][0]
    qr = detect_guide_band(path).rotated(degrees)
    assert item.platform_height == round(qr.bottom*item.height)-round(qr.top*item.height)
    assert item.platform_ry-item.image_ry == round(qr.top*item.height)
    result = generate_layout([path], tmp_path/'out', settings(cutter_mode='single',
        png_engine=engine, manual_rotations=((str(path.resolve()), degrees),)))
    p = result['placements'][0]
    with Image.open(tmp_path/'out'/result['filename']) as output:
        box = (p['platform_x_px'], p['platform_y_px'],
               p['platform_x_px']+p['platform_width_px'], p['platform_y_px']+p['platform_height_px'])
        assert output.crop(box).getchannel('A').getbbox() is not None


def test_missing_qr_warns_without_blocking_and_sequence_is_not_duplicated(tmp_path):
    path = tmp_path/'missing.png'
    Image.new('RGBA', (180, 250), 'blue').save(path, dpi=(25.4, 25.4))
    result = generate_layout([path], tmp_path/'out', settings())
    assert (tmp_path/'out'/result['filename']).exists()
    assert result['placements'][0]['platform_width_px'] == 0
    assert result['analysis']['image_anomalies'][0]['source'] == path.name
    assert numbered_template(settings(label_text_template='{编号} CY')) == '{编号} CY'
    assert numbered_template(settings(label_sequence_enabled=False)) == 'CY'
    assert numbered_template(settings(label_machine_enabled=True)) == 'CY {机器号} {编号}'
    assert numbered_template(settings(label_machine_enabled=True,
        label_text_template='CY {机器号} {编号}')) == 'CY {机器号} {编号}'
    badge = platform_badge('隆丰', 40)
    assert badge.height == 40
    assert badge.getchannel('A').getbbox()[3]-badge.getchannel('A').getbbox()[1] >= 38
    badge.close()


def test_qr_reuse_never_falls_back_to_cutter_lane(tmp_path, monkeypatch):
    from automatic_print.layout_engine import platform_label
    path = qr_image(tmp_path/'B1-1-T-Black-M-NO1-1.png')
    monkeypatch.setattr(platform_label, 'header_space', lambda *_a, **_k: None)
    assert platform_label.platform_geometry(
        path, settings(platform_reuse_qr=True), 180, 250, 0
    ) == (0, 0, 0, 0)


def test_batch_labels_use_global_forward_and_reverse_numbers(tmp_path):
    paths = [qr_image(tmp_path/f'输入图{i}.png') for i in range(1, 4)]
    payloads = []
    generate_layout(paths, tmp_path/'out', settings(
        label_source_order_enabled=True), plan_ready=payloads.append)
    labels = payloads[0]['labels']
    assert '输入图1.png · 正序 1/3 · 倒序 3/3' in labels[1]
    assert '输入图2.png · 正序 2/3 · 倒序 2/3' in labels[2]
    assert '输入图3.png · 正序 3/3 · 倒序 1/3' in labels[3]


@pytest.mark.parametrize('engine', ['pillow', 'libvips'])
def test_parallel_segments_keep_global_numbers_and_platform_coordinates(tmp_path, engine):
    paths = [qr_image(tmp_path/f'B{i}-1-T-Black-M-NO1-1.png') for i in range(4)]
    result = generate_layout(paths, tmp_path/'out', settings(png_engine=engine,
        output_parts=2, save_parallelism=2, save_memory_unlimited=True,
        label_machine_enabled=True, machine_number='M11'))
    assert all(part['machine_number'] == 'M11' for part in result['parts'])
    assert result['actual_save_parallelism'] == 2
    assert sorted(p['sequence_number'] for p in result['placements']) == [1, 2, 3, 4]
    for part in result['parts']:
        assert part['cut_corridor']['pixel_verified']
        with Image.open(tmp_path/'out'/part['filename']) as output:
            for p in part['placements']:
                qr = detect_guide_band(tmp_path/p['source'])
                assert p['platform_y_px'] == p['y_px']+round(qr.top*p['height_px'])
                box = (p['platform_x_px'], p['platform_y_px'],
                    p['platform_x_px']+p['platform_width_px'], p['platform_y_px']+p['platform_height_px'])
                assert output.crop(box).getchannel('A').getbbox() is not None
