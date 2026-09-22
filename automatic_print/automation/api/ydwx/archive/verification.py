"""Verify a published UV split against its original ZIP before reuse."""

import json
import zlib
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from automatic_print.layout_engine.intake.discovery.discovery import SUPPORTED_EXTENSIONS


def verify_existing_split(target, archive_path, spec, capacity):
    try:
        manifest = json.loads((target / "分组信息.json").read_text(encoding="utf-8"))
        archive_stat = archive_path.stat()
        if (manifest["archive"], manifest["archive_bytes"], manifest["archive_mtime_ns"],
                manifest["material"], manifest["capacity"]) != (
                archive_path.name, archive_stat.st_size, archive_stat.st_mtime_ns,
                spec.label, capacity):
            raise ValueError("源 ZIP 或材质已变化")
        files = manifest["files"]
        if len(files) != manifest["image_count"]:
            raise ValueError("分组清单数量不一致")
        with ZipFile(archive_path) as archive:
            source_crcs = {}
            for member in archive.infolist():
                previous = source_crcs.setdefault(member.filename, member.CRC)
                if previous != member.CRC:
                    raise ValueError(f"ZIP 中重名文件内容不一致：{member.filename}")
        for item in files:
            relative = Path(item["path"])
            if relative.is_absolute() or len(relative.parts) != 2 or ".." in relative.parts:
                raise ValueError("分组清单路径异常")
            output = target / relative
            if output.stat().st_size != item["bytes"]:
                raise ValueError(f"{relative} 缺失或大小变化")
            expected_crc = source_crcs.get(item["source"])
            if expected_crc is None or _file_crc32(output) != expected_crc:
                raise ValueError(f"{relative} 内容变化，与原 ZIP 不一致")
        expected_images = {item["path"] for item in files}
        actual_images = {
            path.relative_to(target).as_posix()
            for path in target.rglob("*")
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
        }
        if actual_images != expected_images:
            raise ValueError("分组文件夹存在多余或缺失图片")
        folders = tuple(target / name for name in dict.fromkeys(
            Path(item["path"]).parts[0] for item in files
        ))
        return len(files), folders, str(manifest.get("warning") or "")
    except (KeyError, OSError, TypeError, ValueError, BadZipFile) as error:
        raise ValueError(f"已有分组 {target} 未通过复核：{error}；未覆盖原文件。") from error


def _file_crc32(path):
    checksum = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            checksum = zlib.crc32(chunk, checksum)
    return checksum
