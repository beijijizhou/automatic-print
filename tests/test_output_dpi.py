import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import pytest
from PIL import Image
from automatic_print.layout import LayoutSettings, generate_layout
from automatic_print.layout_engine.output_dpi import resolve_output_dpi


def source(path, dpi=(180,180)):
    with Image.new('RGBA', (180,360), 'blue') as image:
        image.save(path, dpi=dpi)
    return path


@pytest.mark.parametrize('engine', ['pillow','libvips'])
@pytest.mark.parametrize('dpi', [150,180])
def test_follow_preserves_native_pixels_and_physical_dimensions(tmp_path, engine, dpi):
    path = source(tmp_path/'B1-1-T-Black-M-NO1-1.png', (dpi,dpi))
    settings = LayoutSettings(follow_source_dpi=True, dpi=300, margin_mm=0,
        number_images=False, color_block_enabled=False, allow_rotation=False,
        png_engine=engine, png_streaming=True)
    result = generate_layout([path],tmp_path/'out',settings)
    assert result['output_dpi'] == pytest.approx(dpi, abs=.02)
    assert result['output_dpi_origin'] == 'source'
    assert (result['width_px'],result['height_px']) == (180,360)
    assert result['width_mm'] == pytest.approx(180*25.4/dpi, abs=.1)
    with Image.open(tmp_path/'out'/result['filename']) as image:
        assert image.info['dpi'][0] == pytest.approx(dpi, abs=.02)
        assert image.getpixel((90,180)) == (0,0,255,255)


@pytest.mark.parametrize('kind', ['missing','anisotropic'])
def test_invalid_source_dpi_is_not_guessed(tmp_path,kind):
    a=source(tmp_path/'B1-1-T-Black-M-NO1-1.png')
    if kind=='mixed':
        paths=[a,source(tmp_path/'B2-1-T-White-L-NO1-1.png',(150,150))]
    elif kind=='anisotropic':
        paths=[source(a,(150,300))]
    else:
        with Image.new('RGBA',(180,360)) as image:
            image.save(a)
        paths=[a]
    with pytest.raises(ValueError, match='手动指定统一输出DPI'):
        generate_layout(paths,tmp_path/'out',LayoutSettings(follow_source_dpi=True))
    assert not (tmp_path/'out').exists()


@pytest.mark.parametrize('engine',['pillow','libvips'])
def test_mixed_dpi_continues_with_midpoint_and_visible_notice(tmp_path,engine):
    paths=[source(tmp_path/'B1-1-T-Black-M-NO1-1.png',(100,100)),
           source(tmp_path/'B2-1-T-Black-M-NO1-1.png',(200,200))]
    settings=LayoutSettings(follow_source_dpi=True,number_images=False,
        color_block_enabled=False,allow_rotation=False,png_engine=engine)
    result=generate_layout(paths,tmp_path/'out',settings)
    assert result['output_dpi']==150
    assert result['output_dpi_origin']=='mixed_source'
    assert '100 DPI：1张；200 DPI：1张' in result['analysis']['output_dpi_notice']
    assert '中间值 150 DPI' in result['analysis']['output_dpi_notice']
    with Image.open(tmp_path/'out'/result['filename']) as image:
        assert image.info['dpi'][0]==pytest.approx(150,abs=.02)


def test_manual_dpi_does_not_rescan_source_headers(monkeypatch):
    def forbidden(*a,**k): raise AssertionError('manual mode should not scan DPI')
    monkeypatch.setattr(Image,'open',forbidden)
    settings=LayoutSettings(dpi=150)
    assert resolve_output_dpi([Path('unread.png')],settings) is settings


def test_gui_defaults_follow_and_retains_manual_setting(tmp_path):
    from test_developer_mode import window
    owner=window(tmp_path/'prefs.ini')
    assert owner.follow_source_dpi.isChecked()
    assert owner._layout_settings().follow_source_dpi
    assert not owner.dpi.isEnabled()
    owner.follow_source_dpi.setChecked(False)
    owner.dpi.setValue(150)
    owner.preference_autosave.flush()
    owner.close()
    fresh=window(tmp_path/'prefs.ini')
    assert not fresh.follow_source_dpi.isChecked()
    assert fresh.dpi.isEnabled() and fresh.dpi.value()==150
    fresh.follow_source_dpi.setChecked(True)
    assert fresh.dpi.value()==150
    fresh.close()


def test_segments_share_one_resolved_output_dpi(tmp_path):
    paths=[source(tmp_path/f'B{i}-1-T-Black-M-NO1-1.png') for i in range(4)]
    settings=LayoutSettings(follow_source_dpi=True,output_parts=2,
        cutter_mode='single',
        number_images=False,color_block_enabled=True,cutter_left_marker_external=True,allow_rotation=False,
        png_engine='libvips',png_streaming=True,save_memory_unlimited=True)
    result=generate_layout(paths,tmp_path/'out',settings)
    assert result['segment_count']==2
    assert all(p['output_dpi']==result['output_dpi'] for p in result['parts'])
    assert all(p['output_dpi_origin']=='source' for p in result['parts'])


def test_live_preview_uses_the_resolved_source_dpi(tmp_path):
    from test_developer_mode import APP
    from automatic_print.ui.preview_task import PreviewTask
    source(tmp_path/'B1-1-T-Black-M-NO1-1.png',(150,150))
    task=PreviewTask(1,tmp_path,LayoutSettings(follow_source_dpi=True,
        cutter_mode='single',number_images=False,cutter_left_marker_external=True))
    results=[]
    task.signals.finished.connect(lambda token,data,error: results.append((data,error)))
    task.run()
    payload,error=results[0]
    assert not error
    assert payload['settings'].dpi == pytest.approx(150,abs=.02)
    assert payload['settings'].output_dpi_origin == 'source'


def test_missing_dpi_preview_does_not_fall_back_to_guessed_grid(tmp_path):
    from test_developer_mode import APP
    from automatic_print.ui.preview_task import PreviewTask
    with Image.new('RGBA',(180,360)) as image:
        image.save(tmp_path/'B1-1-T-Black-M-NO1-1.png')
    task=PreviewTask(1,tmp_path,LayoutSettings(follow_source_dpi=True))
    results=[]
    task.signals.finished.connect(lambda token,data,error: results.append((data,error)))
    task.run()
    assert results[0][0] is None
    assert '手动指定统一输出DPI' in results[0][1]
