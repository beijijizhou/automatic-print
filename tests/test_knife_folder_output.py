"""The ordinary batch button must not publish mixed-knife PNGs."""

from PIL import Image
import numpy as np

from automatic_print.layout_engine import LayoutSettings
from automatic_print.layout_engine.cutting.geometry.knife_signature import actual_knife_signatures
from automatic_print.layout_engine.cutting.validation.cut_validation import corridor_checks
from automatic_print.ui.workers import GenerateWorker


def test_regular_batch_routes_changed_knife_to_sibling_folder(tmp_path, monkeypatch):
    source = tmp_path / '609182134017'
    source.mkdir()
    for order, width, height in (('BORDER1', 340, 500), ('BORDER2', 200, 150)):
        for side in (1, 2):
            size = 'L' if order == 'BORDER1' else 'S'
            path = source / f'{order}-1-T-Black-{size}-NO1-{side}.png'
            Image.new('RGBA', (width, height), 'blue').save(path, dpi=(25.4, 25.4))
    settings = LayoutSettings(
        dpi=25.4, media_width_mm=600, margin_mm=0, cutter_mode='dual',
        cutter_auto_knife=True, cutter_rotation_zone=True, number_images=False,
        save_parallelism=1,
    )
    monkeypatch.setattr(GenerateWorker, '_save_history', lambda *_: None)
    worker = GenerateWorker(None, source, tmp_path/'排版日志'/'.处理中'/'test',
                            'JOB_TEST', settings)
    completed, failed = [], []
    worker.finished.connect(lambda output, result: completed.append((output, result)))
    worker.failed.connect(failed.append)
    worker.run()
    assert not failed
    output, result = completed[0]
    assert output == str(tmp_path/'切膜机文件')
    assert len(result['parts']) == 2
    assert {name.split('\\')[0].split('/')[0] for name in result['files']} == {'常规', '旋转'}
    assert all('常规+旋转区' not in name for name in result['files'])
    for part in result['parts']:
        assert len(actual_knife_signatures(part)) == 1
        assert part['cut_corridor']['pixel_verified']
        path = tmp_path/'切膜机文件'/part['filename']
        assert path.is_file()
        with Image.open(path) as rendered:
            assert rendered.mode == 'RGBA'
            for check in corridor_checks(part['cut_corridor']):
                stripe = rendered.crop((check['safe_left_px'], check.get('start_y_px', 0),
                                        check['safe_right_px'],
                                        check.get('end_y_px', rendered.height)))
                assert stripe.getchannel('A').getextrema() == (0, 0)
            for placement in part['placements']:
                with Image.open(source/placement['source']) as original:
                    pixels = np.asarray(original.rotate(placement['rotation_degrees'],
                                                       expand=True))
                actual = np.asarray(rendered.crop((
                    placement['x_px'], placement['y_px'],
                    placement['x_px'] + pixels.shape[1],
                    placement['y_px'] + pixels.shape[0],
                )))
                assert np.array_equal(actual[pixels[:, :, 3] > 0],
                                      pixels[pixels[:, :, 3] > 0])
    assert not list((tmp_path/'切膜机文件').glob('*.png'))
