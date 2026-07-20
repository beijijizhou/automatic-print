from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.request import Request, urlopen


LATEST_RELEASE_URL = (
    "https://api.github.com/repos/beijijizhou/automatic-print/releases/latest"
)


@dataclass(frozen=True)
class UpdateInfo:
    version: str
    download_url: str
    release_url: str
    notes: str


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
    return UpdateInfo(
        version=data["tag_name"].removeprefix("v"),
        download_url=(installer or {}).get("browser_download_url", data["html_url"]),
        release_url=data["html_url"],
        notes=data.get("body") or "No release notes were provided.",
    )
