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
from PIL import Image


def _result(*signatures):
    return dict(cutter_mode='dual', output_dpi=300,
                film_width_mm=620,
                placements=[dict(cut_knife_xs_px=signature) for signature in signatures],
                cut_corridor={'pixel_verified': True}, order_check={'orders': 1})


def test_locked_settings_disable_per_batch_knife_and_rotation_search():
    source = LayoutSettings(cutter_mode='dual', media_width_mm=450,
                            cutter_knife_mm=225, cutter_auto_knife=True,
                            cutter_majority_two_zone=True, cutter_rotation_zone=True,
                            cutter_compare_whole_rotation=True)
    locked = locked_knife_settings(source)
    assert locked.cutter_knife_mm == 225
    assert not locked.cutter_auto_knife
    assert locked.strict_fixed_knife
    assert locked.force_small_pair_width
    assert not locked.cutter_majority_two_zone
    assert not locked.cutter_rotation_zone
    assert not locked.cutter_compare_whole_rotation
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
            path = source / f'{index}.png'
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
    path = tmp_path / 'too-wide.png'
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
        path = tmp_path / f'order-size-NO1-{side}.png'
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


def test_one_run_keeps_separate_batches_and_routes_oversize_to_attended(tmp_path, monkeypatch):
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
            path = source / f'{index}.png'
            Image.new('RGB', (width, 300), 'blue').save(path, dpi=(25.4, 25.4))
            paths.append(path)
        prepared.append((source, paths))
    report = render_shared_knife_batches(tmp_path / '隆丰', '隆丰', prepared,
                                          settings, lambda _message: None)
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
    assert {output.parent.name for _files, output in sent} == {'连续打印'}
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
