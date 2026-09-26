from math import ceil, floor

import pytest
from PIL import Image
import numpy as np
from PySide6.QtCore import QSettings

from automatic_print.layout_engine.intake.preparation.item_factory import read_items
from automatic_print.layout_engine.cutting.geometry.cut_guide_geometry import detect_guide_band
from automatic_print.ui.main_window import MainWindow
from test_developer_mode import APP, OWNERS
from test_platform_labels import separate_label_source, settings


def transparent_label_source(path):
    cv2 = pytest.importorskip('cv2')
    qr = Image.fromarray(cv2.QRCodeEncoder_create().encode('POSITION')).convert('RGBA')
    source = Image.new('RGBA', (270, 250))
    source.paste('white', (0, 0, 110, 60))
    source.paste(qr, (75, 10))
    source.save(path, dpi=(25.4, 25.4))
    source.close()
    qr.close()
    return path


def test_qr_row_blank_pixel_check_maps_layout_size_to_source_pixels(tmp_path):
    path = transparent_label_source(tmp_path/'scaled-M-NO1-1.png')
    with Image.open(path) as opened:
        source = opened.copy()
    source.paste('black', (10, 14, 30, 35))
    source.save(path, dpi=(50.8, 50.8))
    source.close()
    from automatic_print.layout_engine.labeling.platform.qr_row_space import is_qr_row_space
    assert not is_qr_row_space(path, 135, 125, 0, (5, 7, 10, 10))
    assert is_qr_row_space(path, 135, 125, 0, (20, 7, 10, 10))


def test_position_designer_updates_all_modes_and_persists(tmp_path):
    preferences = QSettings(str(tmp_path/'position-designer.ini'), QSettings.IniFormat)
    window = MainWindow(preferences)
    OWNERS.append(window)
    window.startup_update_timer.stop()
    label = window.label_settings

    label.position_designer_button.click()
    APP.processEvents()
    designer = label.position_designer
    assert designer.isVisible()
    designer.free.setCurrentIndex(designer.free.findData('bottom_right'))
    designer.vertical.setCurrentIndex(designer.vertical.findData('center'))
    designer.rotated.setCurrentIndex(designer.rotated.findData('right'))

    actual = window._layout_settings()
    assert actual.label_position == 'bottom_right'
    assert actual.cutter_label_vertical_align == 'center'
    assert actual.cutter_label_rotated_align == 'right'
    window.save_layout_preferences(notify=False)
    designer.close()
    window.close()

    restored = MainWindow(preferences)
    OWNERS.append(restored)
    restored.startup_update_timer.stop()
    actual = restored._layout_settings()
    assert actual.label_position == 'bottom_right'
    assert actual.cutter_label_vertical_align == 'center'
    assert actual.cutter_label_rotated_align == 'right'
    restored.close()


@pytest.mark.parametrize('align', ['top', 'center', 'bottom'])
def test_qr_row_space_precedes_unrotated_fallback_alignment(tmp_path, align):
    path = separate_label_source(tmp_path/f'unrotated-{align}-M-NO1-1.png')
    options, _labels = read_items([path], settings(
        cutter_mode='single', platform_reuse_qr=True, preserve_header_gap=True,
        cutter_label_vertical_align=align,
    ), None)
    item = options[0][0]
    from automatic_print.layout_engine.labeling.platform.qr_row_space import is_qr_row_space
    assert is_qr_row_space(path, item.width, item.height, item.rotation_degrees, (
        item.label_rx-item.image_rx, item.label_ry-item.image_ry,
        item.label_width, item.label_height,
    ))


@pytest.mark.parametrize('align', ['left', 'center', 'right'])
def test_cutter_designer_controls_rotated_label_width(tmp_path, align):
    from automatic_print.layout_engine.labeling.platform.membrane_region import MembraneRegion
    from automatic_print.layout_engine.labeling.platform.short_edge_space import short_edge_space
    path = tmp_path/f'rotated-{align}.png'
    Image.new('RGBA', (250, 270)).save(path, dpi=(25.4, 25.4))
    card = MembraneRegion(.1, .65, .7, .9)
    width, height, label_width, label_height = 250, 270, 40, 18
    actual = short_edge_space(
        path, card, width, height, label_width, label_height, 0,
        horizontal_align=align,
    )
    left = ceil(card.left*width)
    right = floor(card.right*width)-label_width
    expected = {'left': left, 'center': (left+right)//2, 'right': right}[align]
    assert actual[0] == expected


@pytest.mark.parametrize('engine', ['pillow', 'libvips'])
@pytest.mark.parametrize('degrees', [0, 90])
def test_designed_cutter_position_is_rendered_without_changing_source_pixels(
        tmp_path, engine, degrees):
    from automatic_print.layout_engine import generate_layout
    path = transparent_label_source(tmp_path/f'output-{engine}-{degrees}-M-NO1-1.png')
    plans = []
    result = generate_layout([path], tmp_path/f'out-{engine}-{degrees}', settings(
        cutter_mode='single', platform_reuse_qr=True, preserve_header_gap=True,
        png_engine=engine, cutter_label_vertical_align='bottom',
        cutter_label_rotated_align='right',
        manual_rotations=((str(path.resolve()), degrees),),
    ), plan_ready=plans.append)
    placement = plans[0]['planned'][0][1]
    with Image.open(path) as source:
        expected = np.asarray(source.rotate(degrees, expand=True))
    with Image.open(tmp_path/f'out-{engine}-{degrees}'/result['filename']) as output:
        actual = np.asarray(output.crop((
            placement.x_px, placement.y_px,
            placement.x_px+placement.width_px,
            placement.y_px+placement.height_px,
        )))
        label = output.crop((
            placement.number_x_px, placement.number_y_px,
            placement.number_x_px+placement.number_width_px,
            placement.number_y_px+placement.number_height_px,
        ))
        assert label.getchannel('A').getbbox() is not None
    from automatic_print.layout_engine.labeling.platform.qr_region import detect_qr_region
    from automatic_print.layout_engine.labeling.platform.qr_row_space import is_qr_row_space
    assert is_qr_row_space(path, placement.width_px, placement.height_px, degrees, (
        placement.number_x_px-placement.x_px,
        placement.number_y_px-placement.y_px,
        placement.number_width_px, placement.number_height_px,
    ))
    qr = detect_qr_region(path).rotated(degrees)
    qr_box = (
        floor(qr.left*placement.width_px), floor(qr.top*placement.height_px),
        ceil(qr.right*placement.width_px), ceil(qr.bottom*placement.height_px),
    )
    assert np.array_equal(
        actual[qr_box[1]:qr_box[3], qr_box[0]:qr_box[2]],
        expected[qr_box[1]:qr_box[3], qr_box[0]:qr_box[2]],
    )
