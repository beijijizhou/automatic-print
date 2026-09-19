"""Assign independently verified cutter files to fixed/change-knife folders."""

from automatic_print.layout_engine.cutting.geometry.knife_signature import (
    actual_knife_signatures, knife_signature,
)


def knife_output_folders(result):
    """Return file-to-folder mapping; never promote a mixed-knife PNG."""
    if result.get('cutter_mode') != 'dual':
        return None
    placements = result.get('placements') or ()
    regular = next((placement for placement in placements
                    if placement.get('cut_zone') != '旋转区'), None)
    fixed = knife_signature(regular) if regular is not None else None
    parts = result.get('parts') or [result]
    folders = {}
    for part in parts:
        if not part.get('order_check'):
            raise ValueError(f"{part['filename']} 缺少订单安全复核，不能归档。")
        corridor = part.get('cut_corridor') or {}
        if not corridor.get('pixel_verified'):
            raise ValueError(f"{part['filename']} 缺少实际像素刀位复核，不能归档。")
        signatures = actual_knife_signatures(part)
        if len(signatures) != 1:
            raise ValueError(f"{part['filename']} 含不同实际刀位，不能放入切膜机文件。")
        signature = next(iter(signatures))
        folders[part['filename']] = '常规' if fixed is not None and signature == fixed else '旋转'
    return folders
