from pathlib import Path

import numpy as np
from PIL import Image
import pytest

from automatic_print.layout_engine import qr_corners
from automatic_print.layout_engine.cut_guide_geometry import detect_guide_band
from automatic_print.layout_engine.qr_detection import detect_qr_location
from automatic_print.layout_engine.membrane_region import detect_membrane_region


@pytest.mark.parametrize('side', ['left', 'right'])
def test_real_header_corners_share_boundary_and_center(tmp_path, side, monkeypatch):
    cv2 = pytest.importorskip('cv2')
    qr = Image.fromarray(cv2.QRCodeEncoder_create().encode('CORNER123')).resize(
        (174, 174), Image.Resampling.NEAREST).convert('RGBA')
    source = Image.new('RGBA', (1000, 1400))
    x = 40 if side == 'left' else 780
    source.paste(qr, (x, 30))
    source.paste('blue', (100, 400, 900, 1400))
    path = tmp_path/f'{side}.png'
    source.save(path)
    original, calls = qr_corners._detect_points, []
    def counted(gray):
        calls.append(gray.shape)
        return original(gray)
    monkeypatch.setattr(qr_corners, '_detect_points', counted)
    band = detect_guide_band(path)
    assert band is not None
    count = len(calls)
    center = detect_qr_location(path)
    assert center.x_ratio == pytest.approx((band.left+band.right)/2)
    assert center.y_ratio == pytest.approx((band.top+band.bottom)/2)
    assert len(calls) == count
    assert detect_membrane_region(path) is not None
    assert len(calls) == count
    assert (center.x_ratio < .5) == (side == 'left')
    assert center.y_ratio < .2
    # All detector inputs are bounded corner crops, never a full-source scan.
    assert all(h*w < 1000*1400/2 for h, w in calls)


def test_missing_header_does_not_search_lower_artwork(tmp_path):
    cv2 = pytest.importorskip('cv2')
    qr = Image.fromarray(cv2.QRCodeEncoder_create().encode('NOT-A-HEADER')).resize(
        (100, 100), Image.Resampling.NEAREST)
    source = Image.new('RGBA', (1000, 1400))
    source.paste(qr, (450, 1200))
    path = tmp_path/'bottom.png'
    source.save(path)
    assert detect_guide_band(path) is None
    assert detect_qr_location(path) is None


def test_crop_scaling_restores_full_source_coordinates(tmp_path, monkeypatch):
    path = tmp_path/'scaled.png'
    source = Image.new('RGBA', (4000, 6000), 'white')
    source.paste('black', (100, 100, 400, 400))
    source.save(path)
    calls = []
    def points(gray):
        calls.append(gray.shape)
        return np.array([[100, 100], [200, 100], [200, 200], [100, 200]], np.float32)
    monkeypatch.setattr(qr_corners, '_detect_points', points)
    region = qr_corners.detect_source_corners(Path(path))
    assert calls == [(1200, 1200)]
    assert region.left == pytest.approx(.05)
    assert region.top == pytest.approx(1/30)
    assert region.right == pytest.approx(.10)
    assert region.bottom == pytest.approx(1/15)
