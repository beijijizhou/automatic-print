import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import pytest
import numpy as np
from PIL import Image
from automatic_print.layout import LayoutSettings, generate_layout
from automatic_print.layout_engine.transition_marks import transition_rects


def test_preview_uses_same_end_block_rectangle():
    from types import SimpleNamespace
    from PySide6.QtGui import QImage,QPainter
    from automatic_print.layout_engine.models import Placement
    from automatic_print.ui.cut_guide_preview import _transition_lines
    p=Placement('a.png',1,20,0,100,140,0,0,0,0,0,120,140)
    planned=[(Path('a.png'),p)]
    settings=LayoutSettings(dpi=25.4,media_width_mm=580,batch_end_block=True,transition_lines=False)
    block=transition_rects(planned,settings,120)[0]
    assert block['x']+block['width']==580
    preview=SimpleNamespace(render_settings=settings,batch_payload={'planned':planned},
        planned=planned,canvas_width=580)
    image=QImage(580,160,QImage.Format_RGBA8888)
    image.fill(0)
    painter=QPainter(image)
    try:
        _transition_lines(preview,painter)
    finally:
        painter.end()
    assert image.pixelColor(block['x'],block['y']).getRgb()==(255,0,0,255)
    assert image.pixelColor(0,block['y']).alpha()==0


@pytest.mark.parametrize('engine',['pillow','libvips'])
@pytest.mark.parametrize('mode',['free','single','dual'])
def test_end_block_only_last_segment_and_source_pixels_preserved(tmp_path,engine,mode):
    paths=[]
    for order in range(4):
        for face in (1,2):
            path=tmp_path/f'B{order}-1-T-Black-M-NO1-{face}.png'
            with Image.new('RGBA',(100,140),(10,20,30,255)) as source:
                source.save(path,dpi=(25.4,25.4))
            paths.append(path)
    settings=LayoutSettings(dpi=25.4,media_width_mm=580,cutter_mode=mode,
        cutter_auto_knife=True,cutter_left_marker_external=True,
        number_images=False,allow_rotation=False,batch_end_block=True,
        output_parts=3,save_memory_unlimited=True,png_engine=engine)
    result=generate_layout(paths,tmp_path/'out',settings)
    assert result['order_check']['double_pairs']==4
    for index,part in enumerate(result['parts']):
        blocks=[r for r in part['transition_marks'] if r['kind']=='批次结束色块']
        assert len(blocks)==int(index==len(result['parts'])-1)
        with Image.open(tmp_path/'out'/part['filename']) as output:
            assert output.width==580
            for p in part['placements']:
                with Image.open(tmp_path/p['source']) as source:
                    crop=output.crop((p['x_px'],p['y_px'],p['x_px']+source.width,p['y_px']+source.height))
                    assert np.array_equal(np.asarray(crop),np.asarray(source))
            if blocks:
                block=blocks[0]
                assert block['x']+block['width']==output.width
                assert output.crop((block['x'],block['y'],block['x']+10,block['y']+10)).getextrema()==((255,255),(0,0),(0,0),(255,255))
                assert block['y']>=max(p['y_px']+p['height_px'] for p in part['placements'])+5
            check=part['cut_corridor']
            for zone in (check.get('zones',[check]) if check else []):
                assert output.crop((zone['safe_left_px'],0,zone['safe_right_px'],output.height)).getchannel('A').getextrema()[1]==0
