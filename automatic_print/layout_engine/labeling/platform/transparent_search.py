"""Check aligned candidate rectangles with one alpha projection per strip."""
from math import ceil, floor
from contextlib import nullcontext

import numpy as np

from automatic_print.layout_engine.measurement.measurement_session import source_pixels
from automatic_print.layout_engine.labeling.platform.membrane_region import MembraneRegion
from automatic_print.layout_engine.measurement.measurement_timing import measured


@measured('透明候选条带扫描')
def clear_rectangles(path, width, height, degrees, rectangles, *, vertical=False, source=None):
    rectangles = tuple(rectangles)
    results = [False] * len(rectangles)
    with (source_pixels(path) if source is None else nullcontext(source)) as source:
        if 'A' not in source.getbands():
            return tuple(w <= 0 or h <= 0 for _, _, w, h in rectangles)
        # Output vertical movement becomes source horizontal movement at 90°.
        moving_y = vertical != bool(degrees % 180)
        groups = {}
        for index, (x, y, w, h) in enumerate(rectangles):
            if w <= 0 or h <= 0:
                results[index] = True
                continue
            if x < 0 or y < 0 or x+w > width or y+h > height:
                continue
            region = MembraneRegion(x/width, y/height,
                                    (x+w)/width, (y+h)/height)
            region = region.rotated((-degrees+180)%360-180)
            box = (max(0, floor(region.left*source.width)-3),
                   max(0, floor(region.top*source.height)-3),
                   min(source.width, ceil(region.right*source.width)+3),
                   min(source.height, ceil(region.bottom*source.height)+3))
            key = (box[0], box[2]) if moving_y else (box[1], box[3])
            groups.setdefault(key, []).append((index, box))
        for entries in groups.values():
            left = min(box[0] for _, box in entries)
            top = min(box[1] for _, box in entries)
            right = max(box[2] for _, box in entries)
            bottom = max(box[3] for _, box in entries)
            with source.crop((left, top, right, bottom)) as crop:
                with crop.getchannel('A') as alpha:
                    occupied = np.asarray(alpha).max(axis=1 if moving_y else 0) > 0
            prefix = np.r_[0, np.cumsum(occupied, dtype=np.int64)]
            for index, box in entries:
                start, end = ((box[1]-top, box[3]-top) if moving_y
                              else (box[0]-left, box[2]-left))
                results[index] = prefix[end] == prefix[start]
    return tuple(bool(result) for result in results)
