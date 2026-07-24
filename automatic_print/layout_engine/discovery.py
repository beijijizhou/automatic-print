from pathlib import Path


SUPPORTED_EXTENSIONS = {
    ".png", ".tif", ".tiff", ".jpg", ".jpeg", ".jfif", ".webp", ".bmp"
}


def discover_images(folder: Path) -> list[Path]:
    return sorted(
        path
        for path in folder.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    )


def discovered_extensions(folder: Path) -> list[str]:
    return sorted(
        {
            path.suffix.lower() or "无扩展名"
            for path in folder.rglob("*")
            if path.is_file()
        }
    )
