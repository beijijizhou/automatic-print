"""Repeatable administrator-only sync from after-sales private config to Supabase."""

import argparse
import json
import subprocess
import tomllib
from pathlib import Path


PROJECT_REF = "bhhbztpmwlzuzbzfmsos"
LOCAL_FIELDS = {
    "Haloo": ("token",),
    "隆丰": ("token",),
    "莆田": ("token",),
    "一朵云": ("username", "password"),
    "七创": ("username", "password"),
    "汉森": ("username", "password", "client_id"),
    "方果": ("username", "password", "tenant_id"),
}
SDS_PROFILES = {"SDS1": "1号线", "SDS2": "2号线"}
SDS_FIELDS = ("contact_tel", "extraInfo", "factory_code", "password")


def collect_profiles(after_sales_root: Path) -> dict:
    private = after_sales_root / ".streamlit"
    local = _read_profiles(private / "local_factory_credentials.toml")
    shared = _read_profiles(private / "secrets.toml")
    profiles = {}
    for platform, fields in LOCAL_FIELDS.items():
        profiles[platform] = _select(local, platform, fields)
    fingerprint = str(local["方果"].get("fingerprint") or "").strip()
    if fingerprint:
        profiles["方果"]["fingerprint"] = fingerprint
    for platform, source in SDS_PROFILES.items():
        profiles[platform] = _select(shared, source, SDS_FIELDS)
    return profiles


def _read_profiles(path):
    with path.open("rb") as stream:
        return tomllib.load(stream).get("factory_credentials", {})


def _select(profiles, platform, fields):
    source = profiles.get(platform) or {}
    missing = [field for field in fields if not str(source.get(field) or "").strip()]
    if missing:
        raise ValueError(f"{platform} 凭据缺少字段：{', '.join(missing)}；未覆盖服务端配置")
    return {field: str(source[field]).strip() for field in fields}


def synchronize(profiles, project_ref=PROJECT_REF):
    secret = "DTF_PLATFORM_CREDENTIALS_JSON=" + json.dumps(
        profiles, ensure_ascii=False, separators=(",", ":"))
    result = subprocess.run(
        ["npx", "--yes", "supabase@latest", "secrets", "set",
         secret, "--project-ref", project_ref],
        capture_output=True, text=True, check=False,
    )
    if result.returncode:
        raise RuntimeError(
            f"DTF 平台凭据同步未完成（CLI 退出 {result.returncode}）；"
            "请核对 Supabase 连接并重试，原服务端配置未主动清除。")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--after-sales-root", type=Path,
        default=Path.home() / "Desktop" / "after-sales",
    )
    parser.add_argument("--project-ref", default=PROJECT_REF)
    args = parser.parse_args(argv)
    profiles = collect_profiles(args.after_sales_root)
    synchronize(profiles, args.project_ref)
    print(f"已同步 {len(profiles)} 个 DTF 平台凭据；赛博已排除，S2B 使用独立服务。")


if __name__ == "__main__":
    main()
