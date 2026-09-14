import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from dataclasses import replace
from pathlib import Path
from math import floor

from PIL import Image
import pytest
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from automatic_print.layout import LayoutSettings
from automatic_print.layout_engine.cut_guide_geometry import guide_spans
from automatic_print.layout_engine.membrane_region import MembraneRegion
from automatic_print.layout_engine.planner import plan_layout
from automatic_print.ui.pair_preview import PairProductionPreview
from automatic_print.ui.preview_snapshot import install_snapshot


def sample(tmp_path):
    paths=[]
    for i in range(2):
        path=tmp_path/f'B{i}-1-T-White-M-NO1-1.png'
        Image.new('RGBA',(180,250),'blue').save(path,dpi=(25.4,25.4))
        paths.append(path)
    settings=LayoutSettings(dpi=25.4,cutter_mode='dual',number_images=False,
                            cutter_auto_knife=False,cutter_rotation_zone=False,margin_mm=0)
    planned,labels,*_=plan_layout(paths,settings,None)
    return paths,settings,planned,labels


def test_shared_row_uses_intersection_and_never_guesses_missing_qr(tmp_path):
    paths,settings,planned,_=sample(tmp_path)
    bands={paths[0]:MembraneRegion(.5,.02,.9,.2),paths[1]:MembraneRegion(.6,.04,.9,.16)}
    spans=guide_spans(planned,settings,bands)
    assert len(spans)==1
    assert (spans[0].top,spans[0].bottom)==(10,40)
    assert spans[0].knife_x==300
    assert not guide_spans(planned,settings,{paths[0]:bands[paths[0]]})
    assert not guide_spans(planned,settings,{**bands,paths[1]:MembraneRegion(.6,.3,.9,.4)})


@pytest.mark.parametrize('degrees,expected',[(0,(10,30)),(90,(20,60)),(-90,(140,180)),(180,(170,190))])
def test_band_tracks_real_rotation_and_zone_knife(tmp_path,degrees,expected):
    paths,settings,planned,_=sample(tmp_path)
    path,p=planned[0]
    p=replace(p,rotation_degrees=degrees,width_px=300,height_px=200,
              cut_zone='旋转区',cut_knife_x_px=400)
    bands={path:MembraneRegion(.7,.05,.9,.15)}
    span=guide_spans([(path,p)],settings,bands)[0]
    assert (span.top,span.bottom)==expected
    assert span.knife_x==400


def test_preview_has_red_dots_only_inside_qr_band_without_green_body_overlay(tmp_path):
    app=QApplication.instance() or QApplication([])
    paths,settings,planned,labels=sample(tmp_path)
    preview=PairProductionPreview(lambda:settings)
    install_snapshot(preview,planned,labels,settings)
    for path in paths:
        stat=path.stat()
        preview.cut_guides.values[(path,stat.st_mtime_ns,stat.st_size,0)]=MembraneRegion(.6,.02,.9,.2)
    preview.resize(932,500)
    frame=QImage(preview.size(),QImage.Format_ARGB32)
    preview.render(frame)
    # The canvas is 600 pixels wide at 1.5 preview scale and begins at y=86.
    knife=round(16+300*1.5)
    red=[]
    for y in range(86,round(86+250*1.5)):
        color=frame.pixelColor(knife,y)
        if color.red()>220 and color.green()<70 and color.blue()<70:
            red.append(y)
        if y>170:
            assert color.green()<=color.red()+15  # no green full-height corridor fill
    assert red
    assert min(red)>=floor(86+5*1.5)
    assert max(red)<=round(86+50*1.5)
    assert len(red)<max(red)-min(red)  # explicit gaps between dots
    assert '会写入输出图片' in preview.guide_status
    preview.close()


def test_disabled_knife_dots_do_not_draw_or_search_headers():
    from types import SimpleNamespace
    from PySide6.QtGui import QPainter
    from automatic_print.ui.cut_guide_preview import draw_cut_guides
    settings=LayoutSettings(cutter_knife_dots=False)
    class NoSearch:
        def request(self,*args):
            raise AssertionError('Disabled knife dots must not search image headers')
    preview=SimpleNamespace(render_settings=settings,planned=[],batch_payload=None,cut_guides=NoSearch())
    image=QImage(100,100,QImage.Format_RGBA8888)
    image.fill(0)
    painter=QPainter(image)
    try:
        draw_cut_guides(preview,painter,1)
    finally:
        painter.end()
    assert '刀位由刀码指示' in preview.guide_status
    assert all(image.pixelColor(x,y).alpha()==0 for x in range(100) for y in range(100))
