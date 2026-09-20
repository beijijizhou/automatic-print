"""Split an already verified plan only at complete-order and row boundaries."""

from automatic_print.layout_engine.orders.order_groups import order_key
from automatic_print.layout_engine.cutting.knife_signature import knife_signature


def partition_plan(planned, count, split_by_knife=False):
    orders = {}
    for path, placement in planned:
        orders.setdefault(order_key(path), []).append((path, placement))
    blocks = []
    for members in orders.values():
        start = min(placement.row_y_px for _, placement in members)
        end = max(placement.row_y_px + placement.footprint_height_px
                  for _, placement in members)
        if blocks and start < blocks[-1][1]:
            old_start, old_end, old_members = blocks[-1]
            blocks[-1] = old_start, max(end, old_end), old_members + members
        else:
            blocks.append((start, end, members))
    if not split_by_knife:
        return _partition_blocks(planned, blocks, min(max(1, count), len(blocks)))
    runs = []
    for block in blocks:
        signatures = {knife_signature(placement) for _path, placement in block[2]}
        if len(signatures) != 1:
            raise ValueError('同一完整订单跨越不同刀位，不能拆成独立打印文件。')
        signature = next(iter(signatures))
        if not runs or runs[-1][0] != signature:
            runs.append((signature, [block]))
        else:
            runs[-1][1].append(block)
    count = min(max(count, len(runs)), len(blocks))
    allocation = [1] * len(runs)
    for _ in range(count - len(runs)):
        eligible = [index for index, (_signature, rows) in enumerate(runs)
                    if allocation[index] < len(rows)]
        index = max(eligible, key=lambda candidate: sum(
            end - start for start, end, _members in runs[candidate][1]
        ) / allocation[candidate])
        allocation[index] += 1
    return [part for (_signature, rows), pieces in zip(runs, allocation)
            for part in _partition_blocks(planned, rows, pieces)]


def _partition_blocks(planned, blocks, count):
    partitions, index = [], 0
    for part in range(count):
        remaining = count - part
        target = sum(block[1] - block[0] for block in blocks[index:]) / remaining
        end, weight = index + 1, blocks[index][1] - blocks[index][0]
        while end < len(blocks) - (remaining - 1):
            next_weight = blocks[end][1] - blocks[end][0]
            if abs(weight + next_weight - target) >= abs(weight - target):
                break
            weight += next_weight
            end += 1
        members = {path for block in blocks[index:end] for path, _ in block[2]}
        partitions.append([(path, placement) for path, placement in planned
                           if path in members])
        index = end
    return partitions
