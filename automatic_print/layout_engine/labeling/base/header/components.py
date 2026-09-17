"""Merge sampled light regions into stable header-card candidates."""
import numpy as np


def merge_vertical_sections(boxes, width):
    """Rejoin one corner card split into stacked white sections by printed rules."""
    boxes = list(boxes)
    changed = True
    while changed:
        changed = False
        for first in range(len(boxes)):
            for second in range(first + 1, len(boxes)):
                a, b = boxes[first], boxes[second]
                upper, lower = (a, b) if a[1] <= b[1] else (b, a)
                upper_width, lower_width = upper[2] - upper[0], lower[2] - lower[0]
                narrow = min(upper_width, lower_width)
                overlap = min(upper[2], lower[2]) - max(upper[0], lower[0])
                gap = lower[1] - upper[3]
                same_corner = ((upper[0] < width * .4 and lower[0] < width * .4)
                               or (upper[2] > width * .6 and lower[2] > width * .6))
                combined_height = max(upper[3], lower[3]) - min(upper[1], lower[1])
                if (same_corner and 0 <= gap <= max(3, round(narrow * .03))
                        and overlap >= narrow * .6 and combined_height <= width * .4):
                    boxes[first] = (
                        min(a[0], b[0]), min(a[1], b[1]),
                        max(a[2], b[2]), max(a[3], b[3]),
                    )
                    boxes.pop(second)
                    changed = True
                    break
            if changed:
                break
    return boxes


def connected_components(mask):
    """Bounded fallback using horizontal runs, not a per-pixel Python flood fill."""
    groups, parents, previous = [], [], []

    def root(index):
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    for y, row in enumerate(mask):
        edges = np.flatnonzero(np.diff(np.r_[False, row, False].astype('int8')))
        current = []
        for left, right in zip(edges[::2], edges[1::2]):
            linked = {root(g) for a, b, g in previous if a <= right and b >= left}
            if linked:
                index = min(linked)
                group = groups[index]
                for other in linked-{index}:
                    parents[other] = index
                    box = groups[other]
                    group[0] = min(group[0], box[0])
                    group[1] = min(group[1], box[1])
                    group[2] = max(group[2], box[2])
                    group[4] += box[4]
                group[0] = min(group[0], int(left))
                group[2] = max(group[2], int(right))
                group[3] = y+1
                group[4] += int(right-left)
            else:
                index = len(groups)
                parents.append(index)
                group = [int(left), y, int(right), y+1, int(right-left)]
                groups.append(group)
            current.append((left, right, index))
        previous = current
    return [group for index, group in enumerate(groups) if root(index) == index]
