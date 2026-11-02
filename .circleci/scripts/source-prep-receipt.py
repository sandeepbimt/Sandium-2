#!/usr/bin/env python3
"""Content-addressed receipt for safe reuse of a prepared Brave Android workspace."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

SCHEMA = 1
RECEIPT = Path("brave-work/.sandium/source-preparation-v1.json")
REQUIRED_FILES = (
    "brave-work/.gclient",
    "brave-work/src/DEPS",
    "brave-work/src/brave/DEPS",
    "brave-work/src/brave/package.json",
    "brave-work/src/brave/pnpm-lock.yaml",
    "brave-work/src/brave/.env",
    "brave-work/src/build/config/compiler/compiler.gni",
    "brave-work/src/brave/third_party/reclient_configs/brave_custom/brave_custom.py",
    "brave-work/src/buildtools/reclient_cfgs/python/python_remote_wrapper",
    "brave-work/src/build/config/siso/brave_siso_config.star",
    "brave-work/src/build/config/siso/.sisorc",
    "brave-work/src/build/config/siso/.sisoenv",
    "brave-work/src/build/config/siso/backend_config/google.star",
    "brave-work/src/build/config/siso/backend_config/backend.star",
    "brave-work/src/out/android_Release_arm64/args.gn",
    "brave-work/src/out/android_Release_arm64/args_generated.gni",
    "brave-work/src/out/android_Release_arm64/build.ninja",
    "brave-work/src/chrome/android/BUILD.gn",
    "brave-work/src/chrome/android/java/AndroidManifest.xml",
    "brave-work/src/chrome/android/java/res_base/drawable/ic_launcher.xml",
    ".circleci/scripts/prepare-brave-source.sh",
    ".circleci/scripts/source-prep-receipt.py",
    ".circleci/scripts/apply-sandium-branding.sh",
    ".circleci/scripts/generate-sandium-density-assets.py",
    ".circleci/branding/source/app_icon.png",
    ".circleci/branding/source/layered_app_icon.png",
    ".circleci/branding/source/layered_app_icon_background.png",
)
for density in ("mdpi", "hdpi", "xhdpi", "xxhdpi", "xxxhdpi"):
    for name in ("app_icon.png", "layered_app_icon.png", "layered_app_icon_background.png"):
        REQUIRED_FILES += (
            f"brave-work/src/chrome/android/java/res_chromium_base/mipmap-{density}/{name}",
        )
REQUIRED_FILES += (
    "brave-work/src/chrome/android/java/res_chromium_base/mipmap-nodpi/layered_app_icon_foreground.xml",
    "brave-work/src/chrome/android/java/res_chromium_base/drawable/themed_app_icon.xml",
)

class ReceiptError(Exception):
    pass

def git_value(path: Path, *args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(path), *args], text=True,
            stderr=subprocess.STDOUT,
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ReceiptError(f"git identity check failed for {path}: {exc}") from exc

def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def snapshot(root: Path, brave_tag: str, chromium_pin: str, reapi_address: str) -> dict:
    root = root.resolve()
    src, core = root / "brave-work/src", root / "brave-work/src/brave"
    actual_tag = git_value(core, "describe", "--tags", "--exact-match")
    actual_chromium = git_value(src, "rev-parse", "HEAD")
    if actual_tag != brave_tag:
        raise ReceiptError(f"Brave tag mismatch: expected {brave_tag}, found {actual_tag}")
    if actual_chromium != chromium_pin:
        raise ReceiptError(f"Chromium pin mismatch: expected {chromium_pin}, found {actual_chromium}")
    if not reapi_address.endswith(":443"):
        raise ReceiptError(f"unexpected REAPI endpoint: {reapi_address!r}")
    files = {}
    for rel in REQUIRED_FILES:
        path = root / rel
        if not path.is_file() or path.stat().st_size == 0:
            raise ReceiptError(f"required file missing or empty: {rel}")
        info = path.stat()
        files[rel] = {
            "sha256": digest(path),
            "size": info.st_size,
            "mode": stat.S_IMODE(info.st_mode),
        }
    payload = {
        "schema": SCHEMA,
        "brave_tag": actual_tag,
        "chromium_commit": actual_chromium,
        "reapi_address": reapi_address,
        "files": files,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    payload["fingerprint"] = hashlib.sha256(canonical).hexdigest()
    return payload

def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("write", "verify"))
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--brave-tag", required=True)
    parser.add_argument("--chromium-pin", required=True)
    parser.add_argument("--reapi-address", required=True)
    args = parser.parse_args()
    receipt_path = args.root.resolve() / RECEIPT
    try:
        current = snapshot(args.root, args.brave_tag, args.chromium_pin, args.reapi_address)
        if args.operation == "write":
            atomic_write(receipt_path, (json.dumps(current, indent=2, sort_keys=True) + "\n").encode())
            print(f"BRAVE_PREP_RECEIPT=WRITTEN fingerprint={current['fingerprint']}")
            return 0
        if not receipt_path.is_file():
            raise ReceiptError("portable source-preparation receipt is absent")
        saved = json.loads(receipt_path.read_text(encoding="utf-8"))
        if saved != current:
            raise ReceiptError("pinned source/configuration or prepared-file hashes changed")
        print(f"BRAVE_PREP_RECEIPT=PASS fingerprint={current['fingerprint']}")
        return 0
    except (OSError, ValueError, ReceiptError) as exc:
        print(f"BRAVE_PREP_RECEIPT=MISS reason={exc}")
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
