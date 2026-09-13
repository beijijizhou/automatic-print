"""Keep cutter marks on lane origins while reusing verified transparent pixels."""
from math import floor, ceil
from PIL import Image
from .membrane_region import MembraneRegion


def transparent_rect(path, width, height, degrees, rect):
    x, y, w, h = rect
    if w <= 0 or h <= 0:
        return True
    if x < 0 or y < 0 or x+w > width or y+h > height:
        return False
    region = MembraneRegion(x/width, y/height, (x+w)/width, (y+h)/height)
    region = region.rotated((-degrees+180)%360-180)
    with Image.open(path) as source:
        if 'A' not in source.getbands():
            return False
        box = (max(0, floor(region.left*source.width)-3),
               max(0, floor(region.top*source.height)-3),
               min(source.width, ceil(region.right*source.width)+3),
               min(source.height, ceil(region.bottom*source.height)+3))
        with source.crop(box) as crop:
            return crop.getchannel('A').getextrema()[1] == 0


def can_embed_marker(path, width, height, degrees, block, label, platform):
    bx, by, bw, bh = block
    lx, ly, lw, lh = label
    px, py, pw, ph = platform
    if pw and px < 0:
        return False
    for rect in (block, label):
        x, y, w, h = rect
        if not transparent_rect(path, width, height, degrees, rect):
            return False
        if pw and w and h and x < px+pw and x+w > px and y < py+ph and y+h > py:
            return False
    return bool(bw and bh)


def validate_embedded_marks(planned):
    """Recheck every source rectangle independently of the packing decision."""
    for path, p in planned:
        for x, y, w, h in ((p.color_block_x_px, p.color_block_y_px,
                           p.color_block_width_px, p.color_block_height_px),
                          (p.number_x_px, p.number_y_px,
                           p.number_width_px, p.number_height_px)):
            if w and h and x < p.x_px+p.width_px and x+w > p.x_px and y < p.y_px+p.height_px and y+h > p.y_px:
                if not transparent_rect(path, p.width_px, p.height_px, p.rotation_degrees,
                                        (x-p.x_px, y-p.y_px, w, h)):
                    raise ValueError(f'{path.name}：内置刀码或文字会覆盖原图，禁止输出。')
