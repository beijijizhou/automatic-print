from dataclasses import replace

from PIL import Image
import pytest

from automatic_print.layout_engine import LayoutSettings, generate_layout
from automatic_print.layout_engine.cutting.geometry.cut_guide_geometry import detect_guide_band
from automatic_print.layout_engine.intake.preparation.item_factory import read_items
from automatic_print.layout_engine.labeling.platform.platform_label import (
    numbered_template, placement_badge, platform_badge, platform_text,
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
    assert numbered_template(settings(label_text_template='{编号} CY')) == '{编号} CY'
    assert numbered_template(settings(label_sequence_enabled=False)) == 'CY'
    assert numbered_template(settings(label_machine_enabled=True)) == 'CY {机器号} {编号}'
    assert numbered_template(settings(label_machine_enabled=True,
        label_text_template='CY {机器号} {编号}')) == 'CY {机器号} {编号}'
    badge = platform_badge('隆丰', 40)
    assert badge.height == 40
    assert badge.getchannel('A').getbbox()[3]-badge.getchannel('A').getbbox()[1] >= 38
    badge.close()


def test_qr_card_without_verified_space_skips_platform_text_and_continues(
        tmp_path, monkeypatch):
    from automatic_print.layout_engine.labeling.platform import platform_label, platform_space

    path = qr_image(tmp_path/'A00000002-B7RLBYZ-1-T-LSJ-2-Black-L-NO1-2.png')
    monkeypatch.setattr(
        platform_label, '_largest_card_badge',
        lambda *_args, **_kwargs: (1, 1, 20, 20),
    )
    monkeypatch.setattr(platform_space, 'card_rect_clear', lambda *_args, **_kwargs: False)

    result = generate_layout(
        [path], tmp_path/'out',
        settings(cutter_mode='single', platform_reuse_qr=True),
    )

    assert (tmp_path/'out'/result['filename']).exists()
    assert result['placements'][0]['platform_width_px'] == 0
    anomaly = result['analysis']['image_anomalies'][0]
    assert anomaly['source'] == path.name
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
def test_source_size_badge_uses_largest_space_inside_rotated_qr_card(
        tmp_path, degrees):
    cv2 = pytest.importorskip('cv2')
    qr = Image.fromarray(cv2.QRCodeEncoder_create().encode('SIZE')).convert('RGBA')
    path = tmp_path/'ORDER-1-T-Black-3XL-NO1-1.png'
    source = Image.new('RGBA', (270, 250))
    source.paste('white', (0, 0, 110, 60))
    source.paste(qr, (75, 10))
    source.paste('blue', (0, 70, 270, 250))
    source.save(path, dpi=(25.4, 25.4))
    source.close()
    options, _ = read_items([path], settings(
        cutter_mode='single', platform_reuse_qr=True,
        manual_rotations=((str(path.resolve()), degrees),),
    ), None)
    item = options[0][0]
    source_region = detect_guide_band(path)
    rotated_region = source_region.rotated(degrees)
    source_height = item.width if degrees % 180 else item.height
    maximum = (round(source_region.bottom*source_height)
               - round(source_region.top*source_height))
    font_height = item.platform_width if degrees % 180 else item.platform_height
    assert 0 < font_height <= maximum
    relative_x = item.platform_rx-item.image_rx
    relative_y = item.platform_ry-item.image_ry
    assert relative_x >= round(rotated_region.left*item.width)-1
    assert relative_y >= round(rotated_region.top*item.height)-1
    assert relative_x+item.platform_width <= round(rotated_region.right*item.width)+1
    assert relative_y+item.platform_height <= round(rotated_region.bottom*item.height)+1
    badge = placement_badge(
        '隆丰 · 3XL', item.platform_width, item.platform_height, degrees,
    )
    assert badge.size == (item.platform_width, item.platform_height)
    if degrees == 90:
        assert badge.height > badge.width
    badge.close()


@pytest.mark.parametrize('engine', ['pillow', 'libvips'])
@pytest.mark.parametrize('degrees', [0, 90])
def test_source_size_badge_is_rendered_in_qr_card_for_each_engine(
        tmp_path, engine, degrees):
    cv2 = pytest.importorskip('cv2')
    qr = Image.fromarray(cv2.QRCodeEncoder_create().encode('OUTPUT')).convert('RGBA')
    path = tmp_path/'ORDER-1-T-Black-3XL-NO1-1.png'
    source = Image.new('RGBA', (270, 250))
    source.paste('white', (0, 0, 110, 60))
    source.paste(qr, (75, 10))
    source.paste('blue', (0, 70, 270, 250))
    source.save(path, dpi=(25.4, 25.4))
    source.close()
    result = generate_layout([path], tmp_path/engine, settings(
        cutter_mode='single', platform_reuse_qr=True, png_engine=engine,
        manual_rotations=((str(path.resolve()), degrees),),
    ))
    placement = result['placements'][0]
    assert placement['platform_width_px'] > 0
    region = detect_guide_band(path).rotated(degrees)
    assert placement['platform_x_px'] >= placement['x_px']+round(region.left*placement['width_px'])-1
    assert placement['platform_y_px'] >= placement['y_px']+round(region.top*placement['height_px'])-1
    assert (placement['platform_x_px']+placement['platform_width_px']
            <= placement['x_px']+round(region.right*placement['width_px'])+1)
    assert (placement['platform_y_px']+placement['platform_height_px']
            <= placement['y_px']+round(region.bottom*placement['height_px'])+1)
    with Image.open(tmp_path/engine/result['filename']) as output:
        box = (
            placement['platform_x_px'], placement['platform_y_px'],
            placement['platform_x_px']+placement['platform_width_px'],
            placement['platform_y_px']+placement['platform_height_px'],
        )
        badge = output.crop(box)
        assert badge.getchannel('A').getbbox() is not None
        assert (0, 0, 0, 255) in set(badge.getdata())


def test_qr_reuse_never_falls_back_to_cutter_lane(tmp_path, monkeypatch):
    from automatic_print.layout_engine.labeling.platform import platform_label
    path = qr_image(tmp_path/'B1-1-T-Black-M-NO1-1.png')
    monkeypatch.setattr(platform_label, 'card_space', lambda *_a, **_k: None)
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
