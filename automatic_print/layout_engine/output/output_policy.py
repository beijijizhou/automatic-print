"""Production output compatibility rules shared by UI and rendering."""
from dataclasses import replace


def enforce_output_compatibility(settings, progress=None):
    """RIIN cutter workflows use PNG; safely downgrade a stale TIFF choice."""
    if settings.cutter_mode == 'free' or settings.output_format.lower() != 'tiff':
        return settings, None
    message = (
        'RIIN 切膜链路不支持 TIFF：原值 TIFF，已采用 PNG；'
        '仅改变输出容器，不改变排版坐标、图片尺寸或刀位。'
    )
    if progress:
        progress('输出格式确认', 1, 1, message)
    return replace(settings, output_format='png'), {
        'original': 'TIFF',
        'adopted': 'PNG',
        'impact': '仅改变输出容器；排版坐标、图片尺寸和刀位不变',
        'edit_path': '打印参数 → 输出图片格式',
        'message': message,
    }
