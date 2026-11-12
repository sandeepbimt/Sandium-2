#!/usr/bin/env python3
"""Prepare, seal and clean-restore-test Sandium's upstream-only source checkpoint."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

BASE = "3c8004b0b01a3e7b65daee40d84c971048fe43ae"
BRAVE_TAG = "v1.98.62"
BRAVE_SHA = "44a84b1f89d9a35287289d6a3d493e362f5a5123"
CHROMIUM_TAG = "156.0.8078.74"
CHROMIUM_SHA = "d331de35ca8ab1358c7a17e4bd41627d55eaef51"
SHARD_DIR = "brave-workspace-checkpoint.shards"
SHARD_MANIFEST = "brave-workspace-checkpoint.manifest.json"
CONTRACT_MANIFEST = "sandium-pinned-source-manifest.json"
TEXT_MANIFEST = "brave-work/.sandium/checkpoint-manifest.txt"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run(command: list[str], *, cwd: Path | None = None) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def inspect_source(root: Path, require_graph: bool = True) -> dict[str, str]:
    work = root / "brave-work"
    src = work / "src"
    core = src / "brave"
    if not (work / ".gclient").is_file() or not (work / ".gclient_entries").is_file():
        raise ValueError("gclient manifest/entries missing; source sync is incomplete")
    if not (src / ".git").exists() or not (core / ".git").exists():
        raise ValueError("Chromium or Brave Git metadata missing")
    brave_sha = subprocess.check_output(["git", "-C", str(core), "rev-parse", "HEAD"], text=True).strip()
    brave_tag = subprocess.check_output(["git", "-C", str(core), "describe", "--tags", "--exact-match"], text=True).strip()
    chromium_sha = subprocess.check_output(["git", "-C", str(src), "rev-parse", "HEAD"], text=True).strip()
    package = json.loads((core / "package.json").read_text(encoding="utf-8"))
    chromium_tag = package["config"]["projects"]["chrome"]["tag"]
    if (brave_tag, brave_sha, chromium_tag, chromium_sha) != (BRAVE_TAG, BRAVE_SHA, CHROMIUM_TAG, CHROMIUM_SHA):
        raise ValueError(
            "source pin mismatch: Brave %s/%s Chromium %s/%s"
            % (brave_tag, brave_sha, chromium_tag, chromium_sha)
        )
    required = [
        src / "DEPS",
        src / "build" / "install-build-deps.sh",
        core / "package.json",
    ]
    if require_graph:
        required += [
            src / "out" / "android_Release_arm64" / "build.ninja",
            src / "out" / "android_Release_arm64" / "args.gn",
        ]
    missing = [str(path.relative_to(root)) for path in required if not path.is_file()]
    if missing:
        raise ValueError("required source/config files missing: " + ", ".join(missing))
    gclient_sha = sha256(work / ".gclient")
    return {
        "brave_tag": brave_tag,
        "brave_sha": brave_sha,
        "chromium_tag": chromium_tag,
        "chromium_sha": chromium_sha,
        "gclient_sha256": gclient_sha,
    }


def shard_tool(root: Path) -> Path:
    path = root / ".circleci" / "scripts" / "sandium-checkpoint-shards.py"
    if not path.is_file():
        raise ValueError("checkpoint shard utility missing: " + str(path))
    return path


def validate_source_only_outputs(root: Path) -> dict[str, int]:
    """Reject Sandium build outputs, not APK fixtures bundled with source/deps."""
    work = root / "brave-work"
    out = work / "src" / "out" / "android_Release_arm64"
    objects = list(out.rglob("*.o")) if out.exists() else []
    if objects:
        examples = [str(path.relative_to(root)) for path in objects[:5]]
        raise ValueError("Pinned Data Save must not compile object files; found %d: %s"
                         % (len(objects), ", ".join(examples)))
    apk_output_dir = out / "apks"
    produced_apks = sorted(apk_output_dir.glob("*.apk")) if apk_output_dir.is_dir() else []
    if produced_apks:
        examples = [str(path.relative_to(root)) for path in produced_apks[:5]]
        raise ValueError("Pinned Data Save must not package Sandium APKs; found %d in build output: %s"
                         % (len(produced_apks), ", ".join(examples)))
    source_apks = [path for path in work.rglob("*.apk") if out not in path.parents]
    print("SANDIUM_PINNED_SOURCE_APK_INVENTORY=INFO bundled_source_apks=%d examples=%s"
          % (len(source_apks), ",".join(str(path.relative_to(root)) for path in source_apks[:5]) or "none"))
    return {"compiled_objects": 0, "sandium_apk_outputs": 0, "bundled_source_apks": len(source_apks)}


def prepare(root: Path) -> None:
    source = inspect_source(root, require_graph=True)
    output_counts = validate_source_only_outputs(root)
    meta = {
        "CHECKPOINT_VALID": "true",
        "CHECKPOINT_KIND": "pinned_source",
        "REFERENCE_MODE": "pinned_source",
        "BASE_REFERENCE": BASE,
        "BRAVE_CORE_TAG": source["brave_tag"],
        "BRAVE_CORE_SHA": source["brave_sha"],
        "CHROMIUM_TAG": source["chromium_tag"],
        "CHROMIUM_SHA": source["chromium_sha"],
        "GCLIENT_SHA256": source["gclient_sha256"],
        "TARGET": "android-arm64",
        "BUILD_TYPE": "Release",
        "SOURCE_ONLY": "true",
        "APK_COMPILED": "false",
        "COMPILED_OBJECT_COUNT": "0",
        "CREATED_AT": datetime.now(timezone.utc).isoformat(),
    }
    folder = root / "brave-work" / ".sandium"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "checkpoint-manifest.txt").write_text(
        "".join("%s=%s\n" % item for item in meta.items()), encoding="utf-8"
    )
    print("SANDIUM_PINNED_SOURCE_PREPARE=PASS; no Sandium APK outputs or compiled objects present; bundled source APKs=%d." % output_counts["bundled_source_apks"])
    for key, value in source.items():
        print("SANDIUM_PINNED_SOURCE_%s=%s" % (key.upper(), value))


def seal(root: Path, branch: str, revision: str, workers: int) -> None:
    source = inspect_source(root, require_graph=True)
    shard_manifest_path = root / SHARD_MANIFEST
    shard_dir = root / SHARD_DIR
    if not shard_manifest_path.is_file() or not shard_dir.is_dir():
        raise ValueError("parallel source checkpoint shards or manifest missing")
    run([sys.executable, str(shard_tool(root)), "verify", "--root", str(root),
         "--workers", str(workers), "--zstd-test"])
    shard_data = json.loads(shard_manifest_path.read_text(encoding="utf-8"))
    checkpoint = shard_data.get("checkpoint_manifest", {})
    if checkpoint.get("CHECKPOINT_KIND") != "pinned_source":
        raise ValueError("shard manifest does not identify a pinned_source checkpoint")
    files = []
    candidates = [shard_manifest_path]
    candidates += sorted(path for path in shard_dir.iterdir() if path.is_file())
    candidates.append(root / TEXT_MANIFEST)
    for path in candidates:
        if not path.is_file():
            raise ValueError("checkpoint payload missing: " + str(path))
        files.append({
            "path": path.relative_to(root).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
        })
    created = datetime.now(timezone.utc).isoformat()
    manifest = {
        "schema_version": 1,
        "checkpoint_id": "pinned-source-%s" % (revision[:12] if revision else created.replace(":", "").replace("-", "")),
        "checkpoint_kind": "pinned_source",
        "status": "READY",
        "created_at": created,
        "base_reference": BASE,
        "branch": branch,
        "source": source,
        "build_identity": {},
        "archive": {
            "format": shard_data.get("format"),
            "shard_count": len(shard_data.get("shards", [])),
            "source_bytes": shard_data.get("source_bytes"),
            "archive_bytes": shard_data.get("archive_bytes"),
            "shard_manifest_sha256": sha256(shard_manifest_path),
        },
        "files": files,
    }
    destination = root / CONTRACT_MANIFEST
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, destination)
    run([sys.executable, str(root / ".circleci" / "scripts" / "sandium_checkpoint_contract.py"),
         "validate", str(destination)])
    print("SANDIUM_PINNED_SOURCE_SEAL=PASS id=%s shards=%d bytes=%s" %
          (manifest["checkpoint_id"], len(shard_data.get("shards", [])), shard_data.get("source_bytes")))


def verify(root: Path, workers: int) -> None:
    contract = root / CONTRACT_MANIFEST
    run([sys.executable, str(root / ".circleci" / "scripts" / "sandium_checkpoint_contract.py"),
         "validate", str(contract)])
    run([sys.executable, str(shard_tool(root)), "verify", "--root", str(root),
         "--workers", str(workers), "--zstd-test"])
    manifest = json.loads(contract.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="sandium-source-restore-test-") as temporary:
        restored_root = Path(temporary)
        shutil.copytree(root / SHARD_DIR, restored_root / SHARD_DIR)
        shutil.copy2(root / SHARD_MANIFEST, restored_root / SHARD_MANIFEST)
        run([sys.executable, str(shard_tool(root)), "restore", "--root", str(restored_root),
             "--workers", str(workers)])
        source = inspect_source(restored_root, require_graph=True)
        if source != manifest["source"]:
            raise ValueError("restored source identity differs from sealed manifest")
        restored_meta = (restored_root / TEXT_MANIFEST).read_text(encoding="utf-8")
        if "CHECKPOINT_KIND=pinned_source" not in restored_meta or "APK_COMPILED=false" not in restored_meta:
            raise ValueError("restored checkpoint metadata does not prove source-only state")
        out = restored_root / "brave-work" / "src" / "out" / "android_Release_arm64"
        if any(out.rglob("*.o")):
            raise ValueError("restored source checkpoint unexpectedly contains compiled objects")
        if any((restored_root / "brave-work").rglob("*.apk")):
            raise ValueError("restored source checkpoint unexpectedly contains an APK")
        print("SANDIUM_PINNED_SOURCE_CLEAN_RESTORE=PASS brave=%s chromium=%s" %
              (source["brave_sha"], source["chromium_sha"]))
    print("SANDIUM_PINNED_SOURCE_VERIFY=PASS id=%s" % manifest["checkpoint_id"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "seal", "verify"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--branch", default=os.environ.get("CIRCLE_BRANCH", "unknown"))
    parser.add_argument("--revision", default=os.environ.get("CIRCLE_SHA1", ""))
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        if args.command == "prepare":
            prepare(root)
        elif args.command == "seal":
            seal(root, args.branch, args.revision, args.workers)
        else:
            verify(root, args.workers)
        return 0
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print("SANDIUM_PINNED_SOURCE=FAIL %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
