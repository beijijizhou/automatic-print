"""Download, validate, and extract S2B production-image archives."""
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit
from urllib.request import Request, urlopen
from zipfile import ZipFile

from ....transfer.downloads import PRODUCTION_IMAGE_EXTENSIONS


def download_archive(record, output_root, index, total, progress):
    host = urlsplit(record.download_url).netloc.lower()
    trusted_host = host == "s2bdiy.com" or host.endswith(".s2bdiy.com")
    if not record.download_url.startswith("https://") or not trusted_host:
        raise RuntimeError(f"S2B 批次 {record.batch_number} 返回了不受信任的下载地址。")
    folder = output_root / "S2B" / "ARCHIVES"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{record.batch_number}_{record.archive_name}"
    partial = target.with_suffix(target.suffix + ".未完成")
    request = Request(encoded_download_url(record.download_url), headers={
        "User-Agent": "AutomaticPrint/1"
    })
    try:
        with urlopen(request, timeout=120) as response, partial.open("wb") as stream:
            expected = int(response.headers.get("Content-Length") or 0)
            written = 0
            last_percent = -1
            last_reported_bytes = 0
            while chunk := response.read(1024 * 1024):
                stream.write(chunk)
                written += len(chunk)
                if expected:
                    percent = min(100, int(written * 100 / expected))
                    if percent == last_percent:
                        continue
                    last_percent = percent
                    detail = f" · {percent}%"
                else:
                    if written - last_reported_bytes < 8 * 1024 * 1024:
                        continue
                    last_reported_bytes = written
                    detail = f" · {written / 1024 / 1024:.0f} MiB"
                if progress:
                    progress(
                        f"[{index}/{total}] 正在下载 S2B / "
                        f"{record.batch_number}{detail}"
                    )
        partial.replace(target)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    return target


def encoded_download_url(value):
    parts = urlsplit(value)
    return urlunsplit((
        parts.scheme,
        parts.netloc,
        quote(parts.path, safe="/%:@"),
        quote(parts.query, safe="=&%+/:;,@"),
        quote(parts.fragment, safe="%"),
    ))


def extract_archive(archive, output_root, batch_number):
    destination = output_root / "S2B" / "BATCHES"
    destination.mkdir(parents=True, exist_ok=True)
    with ZipFile(archive) as bundle:
        root = destination.resolve()
        members = bundle.infolist()
        for member in members:
            target = (destination / member.filename).resolve()
            if target != root and root not in target.parents:
                raise RuntimeError(f"S2B 压缩包包含不安全路径：{member.filename}")
        corrupt = bundle.testzip()
        if corrupt:
            raise RuntimeError(f"S2B 压缩包损坏：{corrupt}")
        bundle.extractall(destination)
        roots = {Path(member.filename).parts[0] for member in members if member.filename}
    if len(roots) == 1 and (destination / next(iter(roots))).is_dir():
        return destination / next(iter(roots))
    return destination / batch_number


def existing_batch(output_root, batch_number):
    root = output_root / "S2B" / "BATCHES"
    if not root.is_dir():
        return None
    for folder in root.iterdir():
        if folder.is_dir() and batch_number in folder.name and any(
            path.suffix.lower() in PRODUCTION_IMAGE_EXTENSIONS
            for path in folder.rglob("*")
        ):
            return folder
    return None
