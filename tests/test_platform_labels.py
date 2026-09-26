from dataclasses import replace

from PIL import Image
import pytest

from automatic_print.layout_engine import LayoutSettings, generate_layout
from automatic_print.layout_engine.cutting.geometry.cut_guide_geometry import detect_guide_band
from automatic_print.layout_engine.intake.preparation.item_factory import read_items
from automatic_print.layout_engine.labeling.platform.platform_label import (
    placement_badge, platform_badge, platform_text,
)
from automatic_print.layout_engine.rendering.storage.segmented_output import shift_part
from automatic_print.layout_engine.cutting.validation.cut_validation import validate_cut_corridor


def qr_image(path):
    cv2 = pytest.importorskip('cv2')
    qr = cv2.QRCodeEncoder_create().encode('TEST123')
    image = Image.new('RGBA', (180, 250), 'blue')
    image.paste(Image.fromarray(qr).convert('RGBA'), (10, 10))
    image.save(path, dpi=(25.4, 25.4))
    assert detect_guide_band(path) is not None
    return path


def separate_label_source(path, payload='SIZE'):
    cv2 = pytest.importorskip('cv2')
    qr = Image.fromarray(cv2.QRCodeEncoder_create().encode(payload)).convert('RGBA')
    source = Image.new('RGBA', (270, 250))
    source.paste('white', (0, 0, 110, 60))
    source.paste(qr, (75, 10))
    source.paste('blue', (0, 70, 270, 250))
    source.save(path, dpi=(25.4, 25.4))
    source.close()
    qr.close()
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
            source_height = p.width_px if p.rotation_degrees % 180 else p.height_px
            maximum = round(qr.bottom*source_height)-round(qr.top*source_height)
            font_height = (p.platform_width_px if p.rotation_degrees % 180
                           else p.platform_height_px)
            assert 0 < font_height <= maximum
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
    qr = detect_guide_band(path)
    source_height = item.width if degrees % 180 else item.height
    maximum = round(qr.bottom*source_height)-round(qr.top*source_height)
    font_height = item.platform_width if degrees % 180 else item.platform_height
    assert 0 < font_height <= maximum
    badge = placement_badge(
        platform_text(path, settings()), item.platform_width,
        item.platform_height, degrees,
    )
    badge.close()
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
    badge = platform_badge('隆丰', 40)
    assert badge.height == 40
    assert badge.getchannel('A').getbbox()[3]-badge.getchannel('A').getbbox()[1] >= 38
    badge.close()


def test_qr_card_without_verified_space_skips_platform_text_and_continues(
        tmp_path):
    path = qr_image(tmp_path/'A00000002-B7RLBYZ-1-T-LSJ-2-Black-L-NO1-2.png')
    result = generate_layout(
        [path], tmp_path/'out',
        settings(cutter_mode='single', platform_reuse_qr=True,
                 preserve_header_gap=True),
    )

    assert (tmp_path/'out'/result['filename']).exists()
    assert result['placements'][0]['platform_width_px'] == 0
    anomaly = result['analysis']['image_anomalies'][0]
    assert anomaly['source'] == path.name
    assert '批次及平台尺码' in anomaly['kind']
    assert '继续完成排版' in anomaly['action']


def test_platform_badge_includes_source_size_and_stays_within_qr_height(tmp_path):
    path = qr_image(tmp_path/'ORDER-1-T-Black-3XL-NO1-1.png')
    text = platform_text(path, settings())
    assert text == '隆丰 · 3XL'
    badge = platform_badge(text, 40)
    ink = badge.getchannel('A').getbbox()
    assert badge.height == 40
    assert ink is not None and ink[3]-ink[1] <= 40
    badge.close()


@pytest.mark.parametrize('degrees', [0, 90])
def test_platform_and_size_use_qr_row_blank_space(
        tmp_path, degrees):
    path = separate_label_source(tmp_path/'ORDER-1-T-Black-3XL-NO1-1.png')
    options, labels = read_items([path], settings(
        cutter_mode='single', platform_reuse_qr=True, preserve_header_gap=True,
        manual_rotations=((str(path.resolve()), degrees),),
    ), None)
    item = options[0][0]
    assert '隆丰 · 3XL' in labels[item.index]
    assert item.platform_width == 0
    assert item.label_width > 0 and item.label_height > 0
    x, y = item.label_rx-item.image_rx, item.label_ry-item.image_ry
    from automatic_print.layout_engine.labeling.platform.qr_row_space import is_qr_row_space
    assert is_qr_row_space(path, item.width, item.height, degrees,
                           (x, y, item.label_width, item.label_height))
    assert 0 <= x and x+item.label_width <= item.width


@pytest.mark.parametrize('engine', ['pillow', 'libvips'])
@pytest.mark.parametrize('degrees', [0, 90])
def test_platform_and_size_render_in_blank_card_without_changing_qr(
        tmp_path, engine, degrees):
    path = separate_label_source(tmp_path/'ORDER-1-T-Black-3XL-NO1-1.png', 'OUTPUT')
    plans = []
    result = generate_layout([path], tmp_path/engine, settings(
        cutter_mode='single', platform_reuse_qr=True,
        preserve_header_gap=True, png_engine=engine,
        manual_rotations=((str(path.resolve()), degrees),),
    ), plan_ready=plans.append)
    placement = result['placements'][0]
    item = plans[0]['planned'][0][1]
    assert (placement['number_width_px'], placement['number_height_px']) == (
        item.number_width_px, item.number_height_px)
    assert placement['platform_width_px'] == 0
    assert placement['number_width_px'] > 0
    from automatic_print.layout_engine.labeling.platform.qr_region import detect_qr_region
    qr = detect_qr_region(path).rotated(degrees)
    left = int(qr.left*placement['width_px'])
    top = int(qr.top*placement['height_px'])
    right = int(qr.right*placement['width_px']+1)
    bottom = int(qr.bottom*placement['height_px']+1)
    with Image.open(tmp_path/engine/result['filename']) as output:
        with Image.open(path) as source:
            rotated = source.convert('RGBA').rotate(degrees, expand=True)
            expected = rotated.crop((left, top, right, bottom))
            actual = output.crop((placement['x_px']+left, placement['y_px']+top,
                                  placement['x_px']+right, placement['y_px']+bottom))
            assert expected.tobytes() == actual.tobytes()
            rotated.close()
        label = output.crop((placement['number_x_px'], placement['number_y_px'],
                             placement['number_x_px']+placement['number_width_px'],
                             placement['number_y_px']+placement['number_height_px']))
        assert label.getchannel('A').getbbox() is not None


def test_platform_merge_never_writes_into_source_card(tmp_path):
    from automatic_print.layout_engine.labeling.platform import platform_label
    path = qr_image(tmp_path/'B1-1-T-Black-M-NO1-1.png')
    assert platform_label.platform_geometry(
        path, settings(platform_reuse_qr=True), 180, 250, 0
    ) == (0, 0, 0, 0)


def test_batch_labels_use_global_forward_and_reverse_numbers(tmp_path):
    paths = [qr_image(tmp_path/f'输入图{i}.png') for i in range(1, 4)]
    payloads = []
    generate_layout(paths, tmp_path/'out', settings(
        label_source_order_enabled=True), plan_ready=payloads.append,
        batch_name='609162025022')
    labels = payloads[0]['labels']
    assert '609162025022 · 正序 1/3 · 倒序 3/3' in labels[1]
    assert '609162025022 · 正序 2/3 · 倒序 2/3' in labels[2]
    assert '609162025022 · 正序 3/3 · 倒序 1/3' in labels[3]
    assert all('输入图' not in label for label in labels.values())


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
                    box = (p['platform_x_px'], p['platform_y_px'],
                        p['platform_x_px']+p['platform_width_px'], p['platform_y_px']+p['platform_height_px'])
                    assert output.crop(box).getchannel('A').getbbox() is not None
