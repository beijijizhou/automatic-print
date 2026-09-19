from automatic_print.automation.workflows.shared_knife import (
    actual_knife_signatures, continuous_print_eligibility, locked_knife_settings,
    route_finished_batches,
)
from automatic_print.layout_engine.domain.models import LayoutSettings, mm_to_px
from automatic_print.layout_engine import generate_layout
from automatic_print.layout_engine.planning.zones.pair_width import apply_pair_width_cap
from automatic_print.layout_engine.intake.metadata.images import print_dimensions
from automatic_print.automation.workflows.shared_knife_batches import render_shared_knife_batches
from pathlib import Path
from collections import Counter
from dataclasses import replace
from types import SimpleNamespace
from PIL import Image
import pytest


def _result(*signatures):
    return dict(cutter_mode='dual', output_dpi=300,
                film_width_mm=620,
                placements=[dict(cut_knife_xs_px=signature) for signature in signatures],
                cut_corridor={'pixel_verified': True}, order_check={'orders': 1})


def test_locked_settings_disable_per_batch_knife_and_rotation_search():
    source = LayoutSettings(cutter_mode='dual', media_width_mm=450,
                            cutter_knife_mm=225, cutter_auto_knife=True,
                            cutter_majority_two_zone=True, cutter_rotation_zone=True,
                            cutter_compare_whole_rotation=True,
                            compare_film_sizes=True)
    locked = locked_knife_settings(source)
    assert locked.cutter_knife_mm == 225
    assert not locked.cutter_auto_knife
    assert locked.strict_fixed_knife
    assert locked.force_small_pair_width
    assert not locked.cutter_majority_two_zone
    assert not locked.cutter_rotation_zone
    assert not locked.cutter_compare_whole_rotation
    assert not locked.compare_film_sizes
    assert source.cutter_auto_knife


def test_only_same_one_knife_and_verified_pixels_are_unattended():
    settings = LayoutSettings(cutter_mode='dual', cutter_knife_mm=225)
    knife = mm_to_px(225, 300)
    assert continuous_print_eligibility(_result((knife,), (knife,)), settings)[0]
    assert not continuous_print_eligibility(_result((knife,), (knife, knife + 100)), settings)[0]
    assert not continuous_print_eligibility(_result((knife,), (knife + 1,)), settings)[0]
    unsafe = _result((knife,))
    unsafe['cut_corridor'] = {'pixel_verified': False}
    assert not continuous_print_eligibility(unsafe, settings)[0]
    unsafe_changed = _result((knife + 100,))
    unsafe_changed['cut_corridor'] = {'pixel_verified': False}
    assert '实际输出像素' in continuous_print_eligibility(unsafe_changed, settings)[1]


def test_different_film_reservation_is_not_continuous():
    settings = LayoutSettings(cutter_mode='dual', cutter_knife_mm=225)
    result = _result((mm_to_px(225, 300),))
    result['film_width_mm'] = 600
    assert not continuous_print_eligibility(result, settings)[0]


def test_multiple_batches_route_from_each_real_output():
    settings = LayoutSettings(cutter_mode='dual', cutter_knife_mm=225)
    knife = mm_to_px(225, 300)
    records = [
        {'folder': 'batch-a', 'output': 'ready', 'result': _result((knife,))},
        {'folder': 'batch-b', 'output': 'attended',
         'result': _result((knife, knife + 100))},
    ]
    routes = route_finished_batches(records, settings)
    assert [route.unattended for route in routes] == [True, False]
    assert routes[0].output == 'ready'
    assert '实际纵刀位' in routes[1].reason


def test_all_segments_are_checked():
    settings = LayoutSettings(cutter_mode='dual', cutter_knife_mm=225)
    knife = mm_to_px(225, 300)
    result = _result((knife,), (knife, knife + 100))
    assert actual_knife_signatures(result) == {(knife,), (knife, knife + 100)}
    assert not continuous_print_eligibility(result, settings)[0]


def test_two_longfeng_batches_generate_with_the_same_real_knife(tmp_path):
    settings = LayoutSettings(
        dpi=25.4, media_width_mm=600, cutter_mode='dual',
        cutter_knife_mm=300, cutter_auto_knife=True,
        platform_name='隆丰', number_images=False, margin_mm=0,
        color_block_gap_mm=5, png_engine='pillow', output_parts=2,
    )
    locked = locked_knife_settings(settings)
    signatures = []
    for batch in ('隆丰批次A', '隆丰批次B'):
        source = tmp_path / batch
        source.mkdir()
        paths = []
        for index in range(4):
            path = source / f'B{index + 1}-1-T-Black-XL-NO1-1.png'
            Image.new('RGB', (280, 300 + index * 10), 'blue').save(
                path, dpi=(25.4, 25.4))
            paths.append(path)
        result = generate_layout(paths, tmp_path / f'{batch}-输出', locked)
        eligible, reason = continuous_print_eligibility(result, locked)
        assert eligible, reason
        assert result['order_check']
        signatures.append(actual_knife_signatures(result))
    assert signatures == [{(300,)}, {(300,)}]


def test_strict_fixed_knife_shrinks_oversize_without_changing_knife(tmp_path):
    settings = locked_knife_settings(LayoutSettings(
        dpi=25.4, media_width_mm=600, cutter_mode='dual',
        cutter_knife_mm=300, number_images=False, margin_mm=0,
        color_block_gap_mm=5, png_engine='pillow',
    ))
    path = tmp_path / 'B1-1-T-Black-XL-NO1-1.png'
    Image.new('RGB', (310, 300), 'blue').save(path, dpi=(25.4, 25.4))
    result = generate_layout([path], tmp_path / 'fixed', settings)
    assert continuous_print_eligibility(result, settings)[0]
    assert actual_knife_signatures(result) == {(300,)}
    assert result['placements'][0]['width_px'] == 270
    assert any(row[1].startswith('共刀并排等比缩小：')
               for row in result['analysis']['width_adjustments'])
    with Image.open(path) as original:
        assert original.size == (310, 300)


def test_fixed_knife_uses_same_scale_on_both_faces(tmp_path):
    paths = []
    for side, width in ((1, 310), (2, 280)):
        path = tmp_path / f'B1-1-T-Black-XL-NO1-{side}.png'
        Image.new('RGB', (width, 300), 'blue').save(path, dpi=(25.4, 25.4))
        paths.append(path)
    settings = locked_knife_settings(LayoutSettings(
        dpi=25.4, media_width_mm=580, cutter_mode='dual', cutter_knife_mm=290,
        number_images=False,
    ))
    adjusted = apply_pair_width_cap(paths, settings)
    overrides = dict(adjusted.dimension_overrides)
    ratios = [overrides[str(path.resolve())][0] / print_dimensions(path, settings.dpi).width_mm
              for path in paths]
    assert ratios[0] == ratios[1]
    assert ratios[0] < 1
    assert len(adjusted.width_adjustments) == 2


def test_shared_knife_limit_keeps_wide_double_order_unscaled(tmp_path):
    paths = []
    for side, width in ((1, 311), (2, 280)):
        path = tmp_path / f'B1-1-T-Black-XL-NO1-{side}.png'
        Image.new('RGB', (width, 300), 'blue').save(path, dpi=(25.4, 25.4))
        paths.append(path)
    settings = locked_knife_settings(LayoutSettings(
        dpi=25.4, media_width_mm=600, cutter_mode='dual', cutter_knife_mm=300,
        number_images=False,
    ))
    adjusted = apply_pair_width_cap(paths, settings)
    assert not adjusted.dimension_overrides
    assert not adjusted.width_adjustments


def test_user_pair_limit_controls_s_to_xl_and_shared_knife(tmp_path):
    paths = []
    for size, width in (('XL', 305), ('2XL', 305), ('L', 306)):
        path = tmp_path / f'B{len(paths)+1}-1-T-Black-{size}-NO1-1.png'
        Image.new('RGB', (width, 300), 'blue').save(path, dpi=(25.4, 25.4))
        paths.append(path)
    settings = locked_knife_settings(LayoutSettings(
        dpi=25.4, media_width_mm=600, cutter_mode='dual', cutter_knife_mm=300,
        force_small_pair_source_limit_mm=305, number_images=False,
    ))
    adjusted = apply_pair_width_cap(paths, settings)
    assert set(dict(adjusted.dimension_overrides)) == {str(paths[0].resolve())}
    assert len(adjusted.width_adjustments) == 1


def test_manual_size_choice_controls_shared_knife_scaling(tmp_path):
    paths = []
    for size in ('XL', '2XL', 'L'):
        path = tmp_path / f'B{len(paths)+1}-1-T-Black-{size}-NO1-1.png'
        Image.new('RGB', (305, 300), 'blue').save(path, dpi=(25.4, 25.4))
        paths.append(path)
    settings = locked_knife_settings(LayoutSettings(
        dpi=25.4, media_width_mm=600, cutter_mode='dual', cutter_knife_mm=300,
        force_small_pair_source_limit_mm=305, force_small_pair_sizes=('XL', '2XL'),
        number_images=False,
    ))
    adjusted = apply_pair_width_cap(paths, settings)
    assert set(dict(adjusted.dimension_overrides)) == {
        str(paths[0].resolve()), str(paths[1].resolve())}
    assert not apply_pair_width_cap(paths, replace(
        settings, force_small_pair_sizes=())).dimension_overrides


@pytest.mark.parametrize('limit', [305, 310])
def test_shared_knife_routes_over_limit_to_independent_zone_across_batches(tmp_path, limit):
    settings = LayoutSettings(
        dpi=25.4, media_width_mm=600, cutter_mode='dual', cutter_knife_mm=300,
        platform_name='隆丰', number_images=False, margin_mm=0,
        force_small_pair_source_limit_mm=limit,
        color_block_gap_mm=5, png_engine='pillow', output_parts=1,
    )
    prepared = []
    for batch in ('批次甲', '批次乙'):
        source = tmp_path / batch
        source.mkdir()
        paths = []
        for index, width in enumerate((280, 280, limit + 1), 1):
            path = source / f'B{index}-1-T-Black-M-NO1-1.png'
            Image.new('RGB', (width, 300), 'blue').save(path, dpi=(25.4, 25.4))
            paths.append(path)
        prepared.append((source, paths))
    report = render_shared_knife_batches(tmp_path / '隆丰', '隆丰', prepared,
                                         settings, lambda _message: None)
    assert not report['layout_errors']
    expected = (300,)
    for batch, result in report['batches']:
        routes = report['batch_routes'][batch]['parts']
        assert len(routes) == 2
        assert [Path(route['folder']).parts[0] for route in routes] == ['常规', '旋转']
        assert routes[0]['knife_signature'] == expected
        assert result['order_check']
        assert all(part['cut_corridor']['pixel_verified'] for part in result['parts'])
        assert not any(f'原尺寸 {limit + 1:.2f}' in row[1]
                       for row in result['analysis']['width_adjustments'])
        for route in routes:
            with Image.open(Path(report['output_folder']) / route['folder'] /
                            route['filename']) as output:
                assert output.mode == 'RGBA'


def test_one_run_keeps_separate_batches_and_shrinks_oversize_to_normal(tmp_path, monkeypatch):
    settings = LayoutSettings(
        dpi=25.4, media_width_mm=600, cutter_mode='dual',
        cutter_knife_mm=300, cutter_auto_knife=True,
        platform_name='隆丰', number_images=False, margin_mm=0,
        color_block_gap_mm=5, png_engine='pillow', output_parts=2,
    )
    prepared = []
    for batch, width in (('批次A', 280), ('批次B', 310)):
        source = tmp_path / batch
        source.mkdir()
        paths = []
        for index in range(2):
            path = source / f'B{index + 1}-1-T-Black-XL-NO1-1.png'
            Image.new('RGB', (width, 300), 'blue').save(path, dpi=(25.4, 25.4))
            paths.append(path)
        prepared.append((source, paths))
    report = render_shared_knife_batches(tmp_path / '隆丰', '隆丰', prepared,
                                          settings, lambda _message: None)
    output_root = Path(report['output_folder'])
    assert output_root.name == '切膜机文件'
    assert {path.name for path in output_root.iterdir() if path.is_dir()} == {'常规', '旋转'}
    assert [batch for batch, _result in report['batches']] == ['批次A', '批次B']
    assert not report['layout_errors']
    assert report['batch_routes']['批次A']['unattended']
    assert report['batch_routes']['批次B']['unattended']
    assert '等比缩小' in report['batch_routes']['批次B']['reason']
    wide_result = dict(report['batches'])['批次B']
    assert any(count == 2 for count in Counter(
        placement['row_y_px'] for placement in wide_result['placements']
    ).values())
    for batch, result in report['batches']:
        folder = Path(report['output_folder']) / report['batch_routes'][batch]['folder']
        assert (folder / result['filename']).is_file()
    from automatic_print.automation.api.riin import jobs
    sent = []
    monkeypatch.setattr(jobs, 'generate_prn', lambda files, output, progress:
                        sent.append((files, output)) or {'state': 'completed'})
    printed, errors, skipped = jobs.generate_batch_prns(report, lambda _message: None)
    assert len(printed) == len(sent) == 2 and not errors and not skipped
    assert {output.parent.parent.name for _files, output in sent} == {'常规'}
    from automatic_print.automation.batches.local import discover_batch_folders
    assert not discover_batch_folders(tmp_path / '隆丰')


def test_completed_fixed_knife_outputs_are_not_rediscovered_as_source_batches(tmp_path):
    from automatic_print.automation.batches.local import discover_batch_folders
    root = tmp_path / '隆丰'
    source = root / 'BATCHES' / '609180000001'
    generated = root / '切膜机文件' / '共用刀位_样例' / '连续打印' / '609180000002'
    for folder in (source, generated):
        folder.mkdir(parents=True)
        Image.new('RGB', (20, 20), 'blue').save(folder / 'image.png')
    assert discover_batch_folders(root) == [source]


def test_fixed_candidate_failure_stays_in_rotation_folder(tmp_path, monkeypatch):
    source = tmp_path / '批次C'
    source.mkdir()
    path = source / '0.png'
    Image.new('RGB', (310, 300), 'blue').save(path, dpi=(25.4, 25.4))
    settings = LayoutSettings(
        dpi=25.4, media_width_mm=600, cutter_mode='dual',
        cutter_knife_mm=300, cutter_auto_knife=True,
        force_small_pair_width_mm=0, number_images=False, margin_mm=0,
        color_block_gap_mm=5,
    )
    report = render_shared_knife_batches(tmp_path / '隆丰', '隆丰',
                                         [(source, [path])], settings,
                                         lambda _message: None)
    assert not report['layout_errors']
    route = report['batch_routes']['批次C']
    assert not route['unattended']
    assert Path(route['folder']).parts[0] == '旋转'
    assert '实际纵刀位' in route['reason']
    result = report['batches'][0][1]
    output = Path(report['output_folder']) / route['folder'] / result['filename']
    assert output.is_file()
    from automatic_print.automation.api.riin import jobs
    sent = []
    monkeypatch.setattr(jobs, 'generate_prn', lambda files, target, progress:
                        sent.append((files, target)) or {'state': 'completed'})
    printed, errors, skipped = jobs.generate_batch_prns(report, lambda _message: None)
    assert len(printed) == len(sent) == 1 and not errors and not skipped
    assert sent[0][1].parent.parent.name == '旋转'


def test_unverified_fixed_output_is_not_sent_to_rotation_or_prn(tmp_path, monkeypatch):
    from automatic_print.automation.workflows import shared_knife_batches
    source = tmp_path / '批次E'
    source.mkdir()
    result = _result((mm_to_px(300, 300),))
    result['cut_corridor'] = {'pixel_verified': False}
    monkeypatch.setattr(shared_knife_batches, 'generate_layout',
                        lambda *_args, **_kwargs: result)
    settings = LayoutSettings(cutter_mode='dual', media_width_mm=600,
                              cutter_knife_mm=300)
    report = render_shared_knife_batches(tmp_path / '隆丰', '隆丰',
                                         [(source, [source / '0.png'])], settings,
                                         lambda _message: None)
    assert not report['batches']
    assert not report['batch_routes']
    assert '实际输出像素' in report['layout_errors'][0]['error']


def test_single_unpaired_row_still_routes_to_fixed_knife_normal(tmp_path):
    source = tmp_path / '批次D'
    source.mkdir()
    path = source / 'only.png'
    Image.new('RGB', (120, 180), 'blue').save(path, dpi=(25.4, 25.4))
    settings = LayoutSettings(
        dpi=25.4, media_width_mm=600, cutter_mode='dual',
        cutter_knife_mm=300, number_images=False, margin_mm=0,
        color_block_gap_mm=5,
    )
    report = render_shared_knife_batches(tmp_path / '隆丰', '隆丰',
                                         [(source, [path])], settings,
                                         lambda _message: None)
    route = report['batch_routes']['批次D']
    assert route['unattended']
    assert Path(route['folder']).parts[0] == '常规'
    result = report['batches'][0][1]
    assert len(result['placements']) == 1
    assert actual_knife_signatures(result) == {(300,)}


def test_partition_by_actual_knife_even_when_only_one_output_part_requested():
    from automatic_print.layout_engine.rendering.storage.segmented_output import partition_plan
    planned = []
    for index, knife in enumerate((300, 300, 420, 420), 1):
        path = Path(f'B{index}-1-T-Black-M-NO1-1.png')
        placement = SimpleNamespace(row_y_px=index * 100, footprint_height_px=80,
                                    cut_knife_xs_px=(knife,), cut_knife_x_px=knife)
        planned.append((path, placement))
    parts = partition_plan(planned, 1, split_by_knife=True)
    assert [[path for path, _p in part] for part in parts] == [
        [planned[0][0], planned[1][0]], [planned[2][0], planned[3][0]],
    ]
    same_order = [(Path('B1-1-T-Black-M-NO1-1.png'), planned[0][1]),
                  (Path('B1-1-T-Black-M-NO1-2.png'), planned[2][1])]
    with pytest.raises(ValueError, match='完整订单'):
        partition_plan(same_order, 1, split_by_knife=True)


def test_one_batch_mixed_knife_files_use_two_folders_and_separate_prns(tmp_path, monkeypatch):
    from automatic_print.automation.workflows import shared_knife_batches
    from automatic_print.automation.api.riin import jobs
    source = tmp_path / '批次混合'
    source.mkdir()
    locked = mm_to_px(300, 300)
    filenames = ['fixed-1.png', 'fixed-2.png', 'changed.png']
    parts = []
    for name, knife in zip(filenames, (locked, locked, locked + 100)):
        part = _result((knife,))
        part['filename'] = name
        parts.append(part)

    def fake_generate(_images, output, _settings, *_args, **kwargs):
        if not kwargs.get('split_by_knife'):
            raise ValueError('固定刀位容纳不了全部图片')
        for name in filenames:
            (output / name).write_bytes(b'PNG')
        return {'filename': filenames[0], 'files': filenames, 'parts': parts}

    monkeypatch.setattr(shared_knife_batches, 'generate_layout', fake_generate)
    settings = LayoutSettings(cutter_mode='dual', media_width_mm=600,
                              cutter_knife_mm=300)
    report = render_shared_knife_batches(tmp_path / '隆丰', '隆丰',
                                         [(source, [source / 'image.png'])], settings,
                                         lambda _message: None)
    assert not report['layout_errors']
    route = report['batch_routes']['批次混合']
    assert not route['unattended']
    assert [Path(part['folder']).parts[0] for part in route['parts']] == [
        '常规', '常规', '旋转',
    ]
    for part in route['parts']:
        assert (Path(report['output_folder']) / part['folder'] / part['filename']).is_file()
    sent = []
    monkeypatch.setattr(jobs, 'generate_prn', lambda files, output, progress:
                        sent.append((files, output)) or {'state': 'completed'})
    printed, errors, skipped = jobs.generate_batch_prns(report, lambda _message: None)
    assert len(printed) == len(sent) == 2 and not errors and not skipped
    assert [[path.name for path in files] for files, _output in sent] == [
        filenames[:2], filenames[2:],
    ]
    assert [output.parent.parent.name for _files, output in sent] == ['常规', '旋转']
    def first_group_fails(files, output, _progress):
        if output.parent.parent.name == '常规':
            raise RuntimeError('固定刀位导入失败')
        return {'state': 'completed'}
    monkeypatch.setattr(jobs, 'generate_prn', first_group_fails)
    printed, errors, skipped = jobs.generate_batch_prns(report, lambda _message: None)
    assert len(printed) == len(errors) == 1 and not skipped
    assert printed[0]['folder'].startswith('旋转')


def test_real_fallback_splits_one_batch_at_actual_knife_change(tmp_path):
    source = tmp_path / '批次混合真实'
    source.mkdir()
    paths = []
    for index, (width, height) in enumerate(((180, 300), (180, 310),
                                             (180, 320), (450, 200)), 1):
        path = source / f'B{index}-1-T-Black-M-NO1-1.png'
        Image.new('RGB', (width, height), 'blue').save(path, dpi=(25.4, 25.4))
        paths.append(path)
    settings = LayoutSettings(
        dpi=25.4, media_width_mm=600, cutter_mode='dual',
        cutter_knife_mm=300, cutter_auto_knife=True,
        cutter_majority_two_zone=True, cutter_rotation_zone=True,
        force_small_pair_width_mm=0, number_images=False, margin_mm=0,
        color_block_gap_mm=5, compare_film_sizes=True, output_parts=1,
    )
    report = render_shared_knife_batches(tmp_path / '隆丰', '隆丰',
                                         [(source, paths)], settings,
                                         lambda _message: None)
    assert not report['layout_errors']
    route = report['batch_routes'][source.name]
    assert {Path(part['folder']).parts[0] for part in route['parts']} == {'常规', '旋转'}
    assert len({part['knife_signature'] for part in route['parts']}) == 2
    result = report['batches'][0][1]
    assert sum(len(part['placements']) for part in result['parts']) == len(paths)
    assert all(part['cut_corridor']['pixel_verified'] for part in result['parts'])
    assert 'film_comparison' not in result['analysis']
    for part in route['parts']:
        with Image.open(Path(report['output_folder']) / part['folder'] / part['filename']) as output:
            assert output.mode == 'RGBA' and output.width > 0 and output.height > 0
