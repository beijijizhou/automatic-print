"""Display release metadata without changing numeric update compatibility."""


def release_display(release_date, iteration=0):
    date = release_date or '日期未知'
    return (f'{date} · 第{iteration:02d}次更新' if iteration > 0
            else f'{date} · 历史版本')
