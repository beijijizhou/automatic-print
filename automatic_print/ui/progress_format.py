from __future__ import annotations


def duration_text(seconds: float) -> str:
    minutes, seconds = divmod(max(0, round(seconds)), 60)
    return f"{minutes}分{seconds:02d}秒" if minutes else f"{seconds}秒"


def file_size_text(size: int) -> str:
    if size >= 1_000_000_000:
        return f"{size / 1_000_000_000:.2f} 吉字节"
    return f"{size / 1_000_000:.1f} 兆字节"
