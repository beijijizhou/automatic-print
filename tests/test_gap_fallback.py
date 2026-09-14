import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import numpy as np
import pytest
from PIL import Image
from automatic_print.layout import LayoutSettings,generate_layout
from automatic_print.layout_engine import header_gap,gap_fallback
from test_header_gap import sample


@pytest.mark.parametrize('engine',['pillow','libvips'])
def test_full_double_batch_rolls_back_only_added_rows(tmp_path,monkeypatch,engine):
    monkeypatch.setattr(header_gap,'cache_root',lambda:tmp_path/'cache')
    paths=[sample(tmp_path/f'B{o}-1-T-Black-M-NO1-{f}.png') for o in range(4) for f in (1,2)]
    originals=[p.read_bytes() for p in paths]
    settings=LayoutSettings(dpi=25.4,cutter_mode='single',media_width_mm=330,
        cutter_left_marker_external=True,membrane_gap_mm=40,number_images=False,
        manual_rotations=tuple((str(p.resolve()),90) for p in paths),png_engine=engine)
    plans=[]
    result=generate_layout(paths,tmp_path/'out',settings,plan_ready=plans.append)
    assert result['order_check']['double_pairs']==4
    assert all(r['rollback_added_mm']==32 for r in result['header_gap'])
    assert all(r['added_px']==0 for r in result['header_gap'])
    assert '已回退' in result['analysis']['image_anomalies'][0]['kind']
    assert settings.membrane_gap_mm==40
    with Image.open(tmp_path/'out'/result['filename']) as output:
        for path,p in plans[0]['planned']:
            assert p.color_block_x_px==0
            with Image.open(path) as source:
                rotated=source.rotate(90,expand=True)
                expected=np.asarray(rotated)
                pixels=np.asarray(output.crop((p.x_px,p.y_px,p.x_px+rotated.width,p.y_px+rotated.height)))
                mask=expected[:,:,3]>0
                assert np.max(np.abs(pixels[mask].astype(int)-expected[mask].astype(int))) <= (1 if engine=='libvips' else 0)
    assert [p.read_bytes() for p in paths]==originals


def test_safety_errors_are_not_retried(monkeypatch):
    calls=[]
    def fail(*args):
        calls.append(args)
        raise ValueError('同订单拆散，禁止生产')
    monkeypatch.setattr(gap_fallback,'plan_layout',fail)
    with pytest.raises(ValueError,match='同订单拆散'):
        gap_fallback.plan_with_gap_fallback([Path('/tmp/a.png')],LayoutSettings(),
            [dict(source='/tmp/a.png',added_px=32)])
    assert len(calls)==1


def test_uniform_dual_knife_failure_retries_original_paths(monkeypatch):
    calls=[]
    def plan(paths,settings,*args):
        calls.append(paths)
        if len(calls)==1:
            raise ValueError('整批图片不存在安全的统一双列刀位，请使用单列或更宽的膜。')
        assert paths==[Path('/tmp/source.png').resolve()]
        assert settings.membrane_gap_mm==0
        return [],{},580,200,200
    monkeypatch.setattr(gap_fallback,'plan_layout',plan)
    rows=[dict(source='/tmp/source.png',prepared='/tmp/copy.png',added_px=32,added_mm=32)]
    paths,settings,result=gap_fallback.plan_with_gap_fallback([Path('/tmp/copy.png')],
        LayoutSettings(membrane_gap_mm=40),rows)
    assert len(calls)==2 and rows[0]['rollback_added_mm']==32
