"""Trusted completed-export downloads used by the production transfer flow."""
from dataclasses import dataclass
from pathlib import Path
import shutil
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class RemoteBatch:
    group_name: str
    batch_number: str
    group_dir: Path


class ExportRecordDownload:
    """Playwright-download compatible wrapper for a completed export record."""

    def __init__(self, url: str):
        self.url = url

    def save_as(self, destination) -> None:
        destination = Path(destination)
        parsed = urlsplit(self.url)
        if (parsed.scheme != "https" or not parsed.hostname
                or not parsed.hostname.lower().endswith(".hihumbird.com")):
            raise RuntimeError("Haloo 生产图导出地址不是受信任的 HTTPS 地址。")
        temporary = destination.with_name(destination.name + ".part")
        temporary.unlink(missing_ok=True)
        try:
            request = Request(self.url, headers={"User-Agent": "AutomaticPrint/1"})
            with urlopen(request, timeout=120) as response, temporary.open("wb") as target:
                shutil.copyfileobj(response, target, length=1024 * 1024)
            if temporary.stat().st_size <= 0:
                raise RuntimeError("Haloo 生产图导出文件为空。")
            temporary.replace(destination)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

    def delete(self) -> None:
        return
