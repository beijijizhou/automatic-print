from __future__ import annotations

import json
import re
from dataclasses import dataclass
from urllib.request import Request, urlopen
from .versioning import release_display


LATEST_RELEASE_URL = (
    "https://api.github.com/repos/beijijizhou/automatic-print/releases/latest"
)


@dataclass(frozen=True)
class UpdateInfo:
    version: str
    download_url: str
    release_url: str
    notes: str
    release_date: str = ""
    release_iteration: int = 0

    @property
    def display_version(self) -> str:
        return release_display(self.version, self.release_date, self.release_iteration)


def version_tuple(version: str) -> tuple[int, ...]:
    cleaned = version.strip().lower().removeprefix("v")
    numbers: list[int] = []
    for part in cleaned.split("."):
        digits = "".join(character for character in part if character.isdigit())
        numbers.append(int(digits or 0))
    return tuple(numbers)


def fetch_latest_release(timeout: int = 10) -> UpdateInfo:
    request = Request(
        LATEST_RELEASE_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "AutomaticPrint-UpdateChecker",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        data = json.load(response)

    assets = data.get("assets", [])
    installer = next(
        (
            asset
            for asset in assets
            if asset.get("name", "").lower().endswith(".exe")
        ),
        None,
    )
    iteration = re.search(r'当日更新次数[：:]\s*(\d+)', data.get('body') or '')
    date = re.search(r'发版日期[：:]\s*(\d{4}-\d{2}-\d{2})', data.get('body') or '')
    return UpdateInfo(
        version=data["tag_name"].removeprefix("v"),
        download_url=(installer or {}).get("browser_download_url", data["html_url"]),
        release_url=data["html_url"],
        notes=data.get("body") or "No release notes were provided.",
        release_date=date[1] if date else (data.get("published_at") or "")[:10],
        release_iteration=int(iteration[1]) if iteration else 0,
    )
