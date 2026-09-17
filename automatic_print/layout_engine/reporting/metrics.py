from __future__ import annotations


def basic_ordered_height(
    footprints: list[tuple[int, int]],
    usable_width: int,
    spacing: int,
) -> int:
    """Return the old sequential first-fit layout height."""
    rows: list[int] = []
    row_width = 0
    row_height = 0
    for width, height in footprints:
        required = width + (spacing if row_width else 0)
        if row_width and row_width + required > usable_width:
            rows.append(row_height)
            row_width, row_height = width, height
        else:
            row_width += required
            row_height = max(row_height, height)
    if row_width:
        rows.append(row_height)
    return sum(rows) + spacing * max(0, len(rows) - 1)


def saving_metrics(
    baseline_height_px: int,
    optimized_height_px: int,
    dpi: int,
) -> dict:
    saved_px = max(0, baseline_height_px - optimized_height_px)
    saved_m = saved_px * 25.4 / dpi / 1000
    printable_baseline = max(1, baseline_height_px)
    return {
        "baseline_height_mm": round(
            baseline_height_px * 25.4 / dpi, 1
        ),
        "saved_length_m": round(saved_m, 3),
        "saved_percent": round(saved_px / printable_baseline * 100, 1),
    }


def saving_text(result: dict) -> str:
    saved = result.get("saved_length_m", 0)
    rotations = result.get("rotation_count", 0)
    if saved <= 0:
        suffix = f" · 旋转 {rotations} 张" if rotations else ""
        return f"本次排版长度已是最短{suffix}"
    return (
        f"智能排版节省 {saved:.3f} 米"
        f"（{result.get('saved_percent', 0):.1f}%）"
        f" · 旋转 {rotations} 张"
    )


def gap_report(records):
    if not records:
        return ''
    changed = [record for record in records if record['added_px']]
    rolled = [record for record in records if record.get('rollback_added_mm')]
    details = [
        *(f"{record['filename']}：新增透明空白{record['added_mm']:.2f}毫米"
          for record in changed),
        *(f"{record['filename']}：已回退新增{record['rollback_added_mm']:.2f}毫米；用户设置未修改"
          for record in rolled),
    ]
    return '\n'.join((gap_summary(records), *details))


def gap_summary(records):
    if not records:
        return ''
    changed = [record for record in records if record.get('added_px')]
    warnings = [record for record in records if record.get('warning')]
    rolled = [record for record in records if record.get('rollback_added_mm')]
    already = len(records) - len(changed) - len(warnings) - len(rolled)
    added = ''
    if changed:
        low = min(record['added_mm'] for record in changed)
        high = max(record['added_mm'] for record in changed)
        added = (f' · 每张新增 {low:.2f} 毫米' if abs(high-low) < .005 else
                 f' · 每张新增 {low:.2f}–{high:.2f} 毫米')
    rollback = f' · 已回退 {len(rolled)} 张' if rolled else ''
    return (
        f"膜标签间距：目标 {records[0]['minimum_mm']:g} 毫米 · 共 {len(records)} 张"
        f" · 实际扩充 {len(changed)} 张 · 原本已满足 {max(0, already)} 张"
        f" · 未能扩充 {len(warnings)} 张{rollback}{added}（不缩放原图）"
    )
