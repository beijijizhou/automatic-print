"""Format one consistent user-facing version identity."""


def release_display(version, release_date, iteration=0):
    number = str(version or '版本未知').removeprefix('v')
    date = release_date or '日期未知'
    suffix = f'第{iteration:02d}次更新' if iteration > 0 else '历史版本'
    return f'{number} · {date} · {suffix}'
