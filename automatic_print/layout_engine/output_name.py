"""Portable output names derived from rendered label text."""
import re


def label_output_name(text, batch_name=""):
    if batch_name:
        text = f"{batch_name}_{text}"
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", text)
    name = re.sub(r"\s+", " ", name).strip(" .")
    if name.lower().endswith(".png"):
        name = name[:-4].rstrip(" .")
    name = name or "排版图片"
    reserved = {"CON", "PRN", "AUX", "NUL"}
    reserved.update(f"{prefix}{i}" for prefix in ("COM", "LPT") for i in range(1, 10))
    if name.split(".")[0].upper() in reserved:
        name = "标签_" + name
    while len(name.encode("utf-8")) > 180:
        name = name[:-1]
    return name.rstrip(" .") + ".png"


def batch_directory_name(batch_name, job_id):
    """Keep source identity in a portable, timestamped task directory."""
    return f"{label_output_name(batch_name)[:-4]}_{job_id}"


def batch_output_directory(base, batch_name, job_id):
    name = batch_directory_name(batch_name, job_id)
    path, index = base / name, 2
    while path.exists():
        path = base / f"{name} ({index})"
        index += 1
    return path


def unused_output_path(directory, filename):
    path = directory / filename
    index = 2
    while path.exists():
        path = directory / f"{filename[:-4]} ({index}).png"
        index += 1
    return path
