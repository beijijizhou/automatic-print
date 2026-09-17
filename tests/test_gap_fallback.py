import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import numpy as np
import pytest
from PIL import Image
from automatic_print.layout_engine import LayoutSettings,generate_layout
from automatic_print.layout_engine.labeling.base import header_gap
from automatic_print.layout_engine.planning.zones import gap_fallback
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
    warning = result['analysis']['image_anomalies'][0]['kind']
    assert '补足 40 毫米方案失败' in warning
    assert '采用值：撤销本张新增 32.00 毫米' in warning
    assert '整批继续尝试' in warning
    assert '修改位置：排版设置→膜标签与图案间距' in warning
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


def test_selected_majority_plan_skips_redundant_rotation_overflow_pass(monkeypatch):
    from automatic_print.layout_engine.planning.zones import width_fit
    calls = []
    def plan(_paths, _settings, _progress, analysis):
        calls.append(1)
        analysis({'rotation_comparison': {
            'selected_strategy': '多数并排区 + 剩余旋转区',
        }})
        return [], {}, 580, 200, 200
    monkeypatch.setattr(gap_fallback, 'plan_layout', plan)
    monkeypatch.setattr(
        width_fit, 'fit_rotation_overflow',
        lambda *_args: pytest.fail('多数并排方案已经成立，不应重跑旋转超宽候选'),
    )
    gap_fallback.plan_with_gap_fallback(
        [Path('/tmp/a.png')],
        LayoutSettings(auto_fit_width=True, cutter_compare_whole_rotation=True),
        [],
    )
    assert len(calls) == 1


def test_missing_header_space_retries_with_external_label_footprint(monkeypatch):
    calls = []
    reports = []
    progress = []

    def plan(_paths, settings, _progress, ready):
        calls.append(settings.preserve_header_gap)
        if len(calls) == 1:
            raise ValueError(
                'image.png：膜标签高度带内没有批次标签的透明空位，禁止输出。'
            )
        data = {'image_anomalies': []}
        ready(data)
        reports.append(data)
        return [], {}, 580, 200, 200

    monkeypatch.setattr(gap_fallback, 'plan_layout', plan)
    _paths, settings, _result = gap_fallback.plan_with_gap_fallback(
        [Path('/tmp/image.png')],
        LayoutSettings(preserve_header_gap=True, cutter_mode='dual'),
        [],
        lambda *args: progress.append(args),
    )

    assert calls == [True, False]
    assert not settings.preserve_header_gap
    assert reports[-1]['header_space_recovery']['adopted'] == '整批外置标签占位'
    assert '原值：复用膜标签透明带' in reports[-1]['image_anomalies'][0]['kind']
    assert progress[-1][0] == '膜标签透明空位恢复'


def test_header_space_recovery_still_compares_rotated_overflow(monkeypatch):
    from dataclasses import replace
    from automatic_print.layout_engine.planning.zones import width_fit

    calls = []

    def plan(_paths, settings, _progress, ready):
        calls.append(settings)
        if len(calls) == 1:
            raise ValueError(
                'image.png：膜标签高度带内没有批次标签的透明空位，禁止输出。'
            )
        ready({'image_anomalies': [], 'rotation_comparison': {
            'selected_strategy': '旋转区域',
            'normal_m': 5.2,
        }})
        height = 300 if settings.dimension_overrides else 500
        return [], {}, 580, height, height

    def fitted(_paths, settings, _progress):
        return replace(settings, dimension_overrides=(('/tmp/image.png', (270, 400)),))

    monkeypatch.setattr(gap_fallback, 'plan_layout', plan)
    monkeypatch.setattr(width_fit, 'fit_rotation_overflow', fitted)

    _paths, settings, result = gap_fallback.plan_with_gap_fallback(
        [Path('/tmp/image.png')],
        LayoutSettings(
            preserve_header_gap=True,
            cutter_mode='dual',
            auto_fit_width=True,
            cutter_compare_whole_rotation=True,
        ),
        [],
    )

    assert [row.preserve_header_gap for row in calls] == [True, False, False]
    assert settings.dimension_overrides
    assert result[3] == 300


def test_header_space_fallback_does_not_hide_second_safety_error(monkeypatch):
    calls = []

    def plan(*args):
        calls.append(1)
        if len(calls) == 1:
            raise ValueError('image.png：膜标签高度带内没有批次标签的透明空位，禁止输出。')
        raise ValueError('同订单拆散，禁止生产')

    monkeypatch.setattr(gap_fallback, 'plan_layout', plan)
    with pytest.raises(ValueError, match='同订单拆散'):
        gap_fallback.plan_with_gap_fallback(
            [Path('/tmp/image.png')],
            LayoutSettings(preserve_header_gap=True, cutter_mode='dual'),
            [],
        )
    assert len(calls) == 2


def test_gap_rollback_then_header_space_failure_uses_external_labels(monkeypatch):
    calls = []
    reports = []

    def plan(_paths, settings, _progress, ready):
        calls.append((settings.membrane_gap_mm, settings.preserve_header_gap))
        if len(calls) == 1:
            raise ValueError('当前膜宽不存在安全的自动分栏方案')
        if len(calls) == 2:
            raise ValueError(
                'image.png：膜标签高度带内没有批次标签的透明空位，禁止输出。'
            )
        data = {'image_anomalies': []}
        ready(data)
        reports.append(data)
        return [], {}, 580, 200, 200

    monkeypatch.setattr(gap_fallback, 'plan_layout', plan)
    rows = [dict(
        source='/tmp/source.png', prepared='/tmp/copy.png',
        added_px=32, added_mm=32,
    )]

    _paths, settings, _result = gap_fallback.plan_with_gap_fallback(
        [Path('/tmp/copy.png')],
        LayoutSettings(membrane_gap_mm=40, preserve_header_gap=True),
        rows,
    )

    assert calls == [(40, True), (0, True), (0, False)]
    assert not settings.preserve_header_gap
    assert rows[0]['rollback_added_mm'] == 32
    assert reports[-1]['header_space_recovery']['adopted'] == '整批外置标签占位'
