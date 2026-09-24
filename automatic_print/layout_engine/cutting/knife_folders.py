"""Assign independently verified cutter files to their layout-zone folders."""

from automatic_print.layout_engine.cutting.knife_signature import actual_knife_signatures


def knife_output_folders(result):
    """Return a zone-based folder mapping after validating each cutter file."""
    if result.get('cutter_mode') != 'dual':
        return None
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
        rotation_flags = {
            placement.get('cut_zone') == '旋转区'
            for placement in (part.get('placements') or ())
        }
        if len(rotation_flags) != 1:
            raise ValueError(f"{part['filename']} 混合了常规区和旋转区，不能归档。")
        folders[part['filename']] = '旋转' if next(iter(rotation_flags)) else '常规'
    return folders
