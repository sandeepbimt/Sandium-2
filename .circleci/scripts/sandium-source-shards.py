#!/usr/bin/env python3
"""Versioned source-only Brave/Chromium checkpoints for Sandium source preparation.

These checkpoints contain the pinned source tree, Git metadata, Brave-managed
dependencies, host/build configuration and the GN/Ninja graph. They deliberately
exclude compiled objects and Siso action state; those belong to Full/Fast build
handoffs, not to the source-ready reference.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = 1
WORKERS_MAX = 8
WORK_NAME = "brave-work"
SHARDS_NAME = "brave-source-checkpoint.shards"
MANIFEST_NAME = "brave-source-checkpoint.manifest.json"
PROGRESS_NAME = ".sandium/source-prep-progress.txt"
PINS_NAME = ".sandium/source-pins.env"
OUT_REL = Path("src/out/android_Release_arm64")

OUT_EXCLUDED_DIRS = {
    "obj", "lib.unstripped", "apks", "thinlto-cache",
}
OUT_EXCLUDED_FILES = {
    ".siso_fs_state", ".siso_fs_state.journal", "siso.INFO",
    "siso.INFO.before-stage", "siso_output", "siso_failed_targets",
    ".ninja_log", ".ninja_deps",
}


def fail(message: str) -> "NoReturn":
    print("SANDIUM_SOURCE_CHECKPOINT=FAIL " + message, file=sys.stderr, flush=True)
    raise SystemExit(1)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_kv(path: Path) -> dict[str, str]:
    if not path.is_file():
        fail("required metadata file missing: %s" % path)
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line and "=" in line:
            key, value = line.split("=", 1)
            result[key] = value
    return result


def is_output_excluded(path: Path, work: Path) -> bool:
    try:
        rel = path.relative_to(work)
    except ValueError:
        return True
    parts = rel.parts
    try:
        out_index = parts.index("out")
    except ValueError:
        return False
    if out_index + 1 >= len(parts) or parts[out_index + 1] != "android_Release_arm64":
        return False
    tail = parts[out_index + 2:]
    if not tail:
        return False
    if tail[0] in OUT_EXCLUDED_DIRS or tail[0].startswith(".siso_fs_state"):
        return True
    if tail[0] == "siso.INFO" or tail[0].startswith("siso.INFO."):
        return True
    name = path.name
    if name in OUT_EXCLUDED_FILES or name.endswith(".staging"):
        return True
    if path.is_file() and name.endswith((".o", ".a", ".so", ".d")):
        return True
    return False


def usable_children(path: Path, work: Path) -> list[Path]:
    try:
        items = sorted(path.iterdir(), key=lambda p: os.fsencode(p.name))
    except OSError as exc:
        fail("cannot enumerate %s: %s" % (path, exc))
    return [p for p in items if not is_output_excluded(p, work)]


def logical_size(path: Path, work: Path) -> int:
    if is_output_excluded(path, work):
        return 0
    if path.is_symlink():
        return 0
    if path.is_file():
        try:
            return path.stat(follow_symlinks=False).st_size
        except OSError:
            return 0
    total = 0
    for directory, dirs, files in os.walk(path, followlinks=False):
        base = Path(directory)
        dirs[:] = [d for d in dirs if not is_output_excluded(base / d, work)]
        for filename in files:
            item = base / filename
            if not is_output_excluded(item, work):
                try:
                    total += item.stat(follow_symlinks=False).st_size
                except OSError:
                    pass
    return total


def discover_roots(root: Path, work: Path) -> tuple[list[Path], list[Path]]:
    src = work / "src"
    if not work.is_dir() or not src.is_dir():
        fail("brave-work/src is missing")
    roots: list[Path] = []
    structural = [work, src]

    # Workspace metadata: .gclient, .gclient_entries and .sandium.
    for item in usable_children(work, work):
        if item != src:
            roots.append(item)

    # Chromium and Brave source roots. Keep the output tree separate so that
    # generated build graph files can be retained without compiled outputs.
    for item in usable_children(src, work):
        if item.name != "out":
            roots.append(item)
        else:
            structural.append(item)
            for out_item in usable_children(item, work):
                if out_item.name != "android_Release_arm64":
                    roots.append(out_item)
                    continue
                structural.append(out_item)
                for graph_item in usable_children(out_item, work):
                    roots.append(graph_item)

    required = [
        work / ".gclient",
        work / ".gclient_entries",
        src / ".git",
        src / "brave" / ".git",
        src / "build" / "install-build-deps.sh",
        src / "third_party",
        work / PINS_NAME,
    ]
    for item in required:
        if not item.exists():
            fail("source checkpoint is missing required component: %s" % item)

    if not roots:
        fail("no source checkpoint roots discovered")
    rels = sorted(p.relative_to(root).as_posix() for p in roots)
    for previous, current in zip(rels, rels[1:]):
        if current == previous or current.startswith(previous.rstrip("/") + "/"):
            fail("source checkpoint roots overlap: %s and %s" % (previous, current))
    return roots, structural


def split_heavy(path: Path, work: Path, target: int, depth: int,
                max_depth: int = 5) -> list[Path]:
    size = logical_size(path, work)
    if not path.is_dir() or path.is_symlink() or size <= target or depth >= max_depth:
        return [path]
    children = usable_children(path, work)
    if not children:
        return [path]
    result: list[Path] = []
    for child in children:
        result.extend(split_heavy(child, work, target, depth + 1, max_depth))
    return result or [path]


def plan_roots(roots: list[Path], work: Path, workers: int) -> tuple[list[list[Path]], dict[str, int]]:
    sizes: dict[str, int] = {}
    for path in roots:
        sizes[str(path)] = logical_size(path, work)
    total = sum(sizes.values())
    target = max(1, int((total / max(1, workers)) * 1.15))
    expanded: list[Path] = []
    for path in roots:
        expanded.extend(split_heavy(path, work, target, 0))
    expanded_sizes = {str(p): logical_size(p, work) for p in expanded}
    expanded.sort(key=lambda p: expanded_sizes[str(p)], reverse=True)
    buckets: list[list[Path]] = [[] for _ in range(min(workers, len(expanded)))]
    loads = [0] * len(buckets)
    for path in expanded:
        index = min(range(len(buckets)), key=lambda i: loads[i])
        buckets[index].append(path)
        loads[index] += expanded_sizes[str(path)]
    buckets = [b for b in buckets if b]
    if not buckets:
        fail("source checkpoint produced no archive workers")
    print("SANDIUM_SOURCE_SHARD_PLAN=PASS roots=%d shards=%d source_bytes=%d largest_bucket=%d" %
          (len(expanded), len(buckets), total, max(loads)), flush=True)
    return buckets, expanded_sizes


def source_metadata(root: Path, work: Path, stage: int, ready: bool) -> dict[str, Any]:
    progress = parse_kv(work / PROGRESS_NAME)
    pins = parse_kv(work / PINS_NAME)
    src = work / "src"
    core = src / "brave"
    actual_chromium = subprocess.check_output(
        ["git", "-C", str(src), "rev-parse", "HEAD"], text=True
    ).strip()
    actual_brave = subprocess.check_output(
        ["git", "-C", str(core), "describe", "--tags", "--exact-match"],
        text=True
    ).strip()
    if actual_chromium != pins.get("CHROMIUM_SHA"):
        fail("Chromium SHA does not match source-pins.env")
    if actual_brave != pins.get("BRAVE_CORE_TAG"):
        fail("Brave tag does not match source-pins.env")

    metadata: dict[str, Any] = {
        "source_prep_stage": stage,
        "source_prep_phase": progress.get("PHASE", "unknown"),
        "ready": ready,
        "brave_core_tag": actual_brave,
        "chromium_tag": pins.get("CHROMIUM_TAG", ""),
        "chromium_sha": actual_chromium,
        "gclient_sha256": sha256_file(work / ".gclient"),
        "gclient_entries_sha256": sha256_file(work / ".gclient_entries"),
        "source_pins_sha256": sha256_file(work / PINS_NAME),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    package = core / "package.json"
    lockfile = core / "pnpm-lock.yaml"
    npmrc = core / ".npmrc"
    dep_files = [p for p in [package, lockfile, npmrc] if p.is_file()]
    dep_fingerprint = hashlib.sha256(
        "".join(sha256_file(p) for p in dep_files).encode("ascii")
    ).hexdigest()
    metadata["brave_dependency_fingerprint"] = dep_fingerprint

    if ready:
        out = src / "out" / "android_Release_arm64"
        required_ready = [
            out / "build.ninja", out / "args.gn", out / "args_generated.gni",
            src / "build" / "config" / "siso" / ".sisoenv",
            src / "build" / "config" / "siso" / ".sisorc",
            src / "build" / "config" / "siso" / "backend_config" / "backend.star",
            src / "build" / "config" / "siso" / "brave_siso_config.star",
            src / "buildtools" / "reclient_cfgs" / "python" / "python_remote_wrapper",
            core / "node_modules" / ".modules.yaml",
            core / "node_modules" / ".pnpm",
        ]
        for item in required_ready:
            if not item.exists():
                fail("source-ready archive is missing %s" % item)
        if not os.access(src / "buildtools" / "reclient_cfgs" / "python" / "python_remote_wrapper", os.X_OK):
            fail("Brave Python remote wrapper is not executable")
        args_generated = (out / "args_generated.gni").read_text(encoding="utf-8")
        for key, expected in [
            ("use_remoteexec", "true"), ("use_siso", "true"), ("use_reclient", "false"),
            ("is_official_build", "true"), ("android_aab_to_apk", "true"),
        ]:
            if not any(line.strip() == "%s = %s" % (key, expected) for line in args_generated.splitlines()):
                fail("source-ready generated GN args lack %s=%s" % (key, expected))
        for path in required_ready:
            if path.is_file():
                metadata["sha256:" + str(path.relative_to(work))] = sha256_file(path)
    return metadata


def sha256_file_stream(path: Path) -> str:
    return sha256_file(path)


def archive_worker(index: int, roots: list[Path], root: Path, work: Path,
                   stage_dir: Path) -> dict[str, Any]:
    name = "source-shard-%02d.tar.zst" % index
    destination = stage_dir / name
    temporary = stage_dir / (name + ".tmp")
    list_file = stage_dir / (name + ".roots0")
    with list_file.open("wb") as stream:
        for path in roots:
            stream.write(os.fsencode(path.relative_to(root).as_posix()) + b"\0")

    tar_cmd = [
        "tar", "-c", "--format=posix",
        "--pax-option=delete=atime,delete=ctime",
        "--exclude=*.staging",
        "--exclude=brave-work/src/out/android_Release_arm64/obj",
        "--exclude=brave-work/src/out/android_Release_arm64/lib.unstripped",
        "--exclude=brave-work/src/out/android_Release_arm64/apks",
        "--exclude=brave-work/src/out/android_Release_arm64/thinlto-cache",
        "--exclude=brave-work/src/out/android_Release_arm64/.siso_fs_state",
        "--exclude=brave-work/src/out/android_Release_arm64/.siso_fs_state.journal",
        "--exclude=brave-work/src/out/android_Release_arm64/siso.INFO",
        "--exclude=brave-work/src/out/android_Release_arm64/siso.INFO.before-stage",
        "--exclude=brave-work/src/out/android_Release_arm64/siso_output",
        "--exclude=brave-work/src/out/android_Release_arm64/siso_failed_targets",
        "--exclude=brave-work/src/out/android_Release_arm64/.ninja_log",
        "--exclude=brave-work/src/out/android_Release_arm64/.ninja_deps",
        "--checkpoint=100000",
        "--checkpoint-action=echo=SOURCE_SHARD_%02d_TAR_CHECKPOINT=%%u" % index,
        "-C", str(root), "--null", "-T", str(list_file),
    ]
    started = time.monotonic()
    with tempfile.TemporaryFile() as stderr:
        tar = subprocess.Popen(tar_cmd, stdout=subprocess.PIPE, stderr=stderr)
        assert tar.stdout is not None
        zstd = subprocess.Popen(["zstd", "-T1", "--fast=5", "-q", "-o", str(temporary)],
                                stdin=tar.stdout, stdout=subprocess.DEVNULL)
        tar.stdout.close()
        zstd_rc = zstd.wait()
        tar_rc = tar.wait()
        stderr.seek(0)
        diagnostic = stderr.read().decode("utf-8", "replace").strip()
    list_file.unlink(missing_ok=True)
    if tar_rc != 0 or zstd_rc != 0 or not temporary.is_file() or temporary.stat().st_size == 0:
        temporary.unlink(missing_ok=True)
        raise RuntimeError("source shard %s failed tar=%d zstd=%d: %s" %
                           (name, tar_rc, zstd_rc, diagnostic[-2000:]))
    os.replace(temporary, destination)
    return {
        "name": name,
        "size_bytes": destination.stat().st_size,
        "sha256": sha256_file_stream(destination),
        "archive_seconds": round(time.monotonic() - started, 3),
        "root_paths": [p.relative_to(root).as_posix() for p in roots],
    }


def archive(root: Path, workers: int, stage: int, ready: bool) -> None:
    work = root / WORK_NAME
    progress_path = work / PROGRESS_NAME
    if not progress_path.is_file():
        fail("source preparation progress marker missing")
    roots, structural = discover_roots(root, work)
    metadata = source_metadata(root, work, stage, ready)
    # Split large source trees into disjoint directory roots and distribute them
    # across up to eight tar+zstd workers.
    total_bytes = sum(logical_size(p, work) for p in roots)
    target = max(1, int((total_bytes / workers) * 1.15))
    expanded: list[Path] = []
    for path in roots:
        expanded.extend(split_heavy(path, work, target, 0))
    sizes = {str(p): logical_size(p, work) for p in expanded}
    expanded.sort(key=lambda p: sizes[str(p)], reverse=True)
    count = min(workers, len(expanded))
    buckets: list[list[Path]] = [[] for _ in range(count)]
    loads = [0] * count
    for path in expanded:
        index = min(range(count), key=lambda i: loads[i])
        buckets[index].append(path)
        loads[index] += sizes[str(path)]

    stage_dir = root / (SHARDS_NAME + ".tmp")
    final_dir = root / SHARDS_NAME
    manifest_path = root / MANIFEST_NAME
    shutil.rmtree(stage_dir, ignore_errors=True)
    stage_dir.mkdir(parents=True)
    results: list[dict[str, Any]] = []
    errors: list[str] = []
    print("SANDIUM_SOURCE_ARCHIVE=START stage=%d ready=%s workers=%d source_bytes=%d" %
          (stage, ready, len(buckets), total_bytes), flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(buckets)) as pool:
        futures = [pool.submit(archive_worker, i, bucket, root, work, stage_dir)
                   for i, bucket in enumerate(buckets, 1)]
        for future in concurrent.futures.as_completed(futures):
            try:
                item = future.result()
                results.append(item)
                print("SANDIUM_SOURCE_SHARD=PASS %s bytes=%d seconds=%.1f sha256=%s" %
                      (item["name"], item["size_bytes"], item["archive_seconds"], item["sha256"]),
                      flush=True)
            except Exception as exc:
                errors.append(str(exc))
    if errors:
        shutil.rmtree(stage_dir, ignore_errors=True)
        fail("source archive worker failed; previous checkpoint remains intact: " + "; ".join(errors))

    results.sort(key=lambda item: item["name"])
    total_archive_bytes = sum(item["size_bytes"] for item in results)
    old_dir = root / (SHARDS_NAME + ".previous")
    shutil.rmtree(old_dir, ignore_errors=True)
    if final_dir.exists():
        os.replace(final_dir, old_dir)
    os.replace(stage_dir, final_dir)
    payload = {
        "schema_version": SCHEMA,
        "format": "sandium-brave-source-only-shards",
        "workspace_root": WORK_NAME,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "stage": stage,
        "ready": ready,
        "workers": len(results),
        "max_workers": workers,
        "source_bytes": total_bytes,
        "archive_bytes": total_archive_bytes,
        "excluded_compiled_output": sorted(OUT_EXCLUDED_DIRS),
        "excluded_transient_patterns": [
            "*.staging", "*.o", "*.a", "*.so", "*.d",
            ".siso_fs_state*", "siso.INFO*", ".ninja_log", ".ninja_deps",
        ],
        "source": metadata,
        "shards": results,
    }
    temp_manifest = manifest_path.with_suffix(".json.tmp")
    temp_manifest.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n",
                             encoding="utf-8")
    os.replace(temp_manifest, manifest_path)
    shutil.rmtree(old_dir, ignore_errors=True)
    print("SANDIUM_SOURCE_ARCHIVE=PASS stage=%d ready=%s shards=%d source_bytes=%d archive_bytes=%d" %
          (stage, ready, len(results), total_bytes, total_archive_bytes), flush=True)


def load_manifest(root: Path) -> tuple[dict[str, Any], Path]:
    path = root / MANIFEST_NAME
    if not path.is_file():
        fail("source checkpoint manifest missing: %s" % path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail("cannot parse source checkpoint manifest: %s" % exc)
    if payload.get("schema_version") != SCHEMA or payload.get("format") != "sandium-brave-source-only-shards":
        fail("unsupported source checkpoint manifest schema/format")
    shards = payload.get("shards")
    if not isinstance(shards, list) or not shards or len(shards) > WORKERS_MAX:
        fail("source checkpoint shard list invalid")
    seen: list[str] = []
    for item in shards:
        if not isinstance(item, dict) or not item.get("name"):
            fail("invalid source shard record")
        if Path(item["name"]).name != item["name"]:
            fail("unsafe source shard filename")
        roots = item.get("root_paths")
        if not isinstance(roots, list) or not roots:
            fail("source shard has no owned paths")
        for rel in roots:
            path_obj = Path(rel)
            if path_obj.is_absolute() or ".." in path_obj.parts:
                fail("unsafe source shard path")
            if not (rel == WORK_NAME or rel.startswith(WORK_NAME + "/")):
                fail("source shard path escapes brave-work")
            for prior in seen:
                if rel == prior or rel.startswith(prior.rstrip("/") + "/") or prior.startswith(rel.rstrip("/") + "/"):
                    fail("overlapping source shard paths")
            seen.append(rel)
    return payload, root / SHARDS_NAME


def verify(root: Path, workers: int, zstd_test: bool, require_ready: bool) -> dict[str, Any]:
    payload, shard_dir = load_manifest(root)
    if require_ready and payload.get("ready") is not True:
        fail("checkpoint is a progress archive, not a promoted source-ready archive")
    if require_ready:
        source = payload.get("source", {})
        required = {
            "brave_core_tag": "v1.99.54",
            "chromium_tag": "157.0.8103.30",
        }
        for key, expected in required.items():
            if source.get(key) != expected:
                fail("source-ready pin mismatch %s expected=%s actual=%s" %
                     (key, expected, source.get(key)))
        if len(source.get("chromium_sha", "")) != 40:
            fail("source-ready Chromium SHA is invalid")

    errors: list[str] = []
    def check(item: dict[str, Any]) -> str:
        path = shard_dir / item["name"]
        if not path.is_file():
            raise RuntimeError("missing source shard %s" % path)
        if path.stat().st_size != int(item["size_bytes"]):
            raise RuntimeError("source shard size mismatch %s" % path.name)
        if sha256_file(path) != item["sha256"]:
            raise RuntimeError("source shard SHA256 mismatch %s" % path.name)
        if zstd_test:
            proc = subprocess.run(["zstd", "-t", str(path)], stdout=subprocess.DEVNULL,
                                  stderr=subprocess.PIPE)
            if proc.returncode:
                raise RuntimeError("zstd integrity failure %s: %s" %
                                   (path.name, proc.stderr.decode("utf-8", "replace")[-1000:]))
        return path.name

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(workers, len(payload["shards"]))) as pool:
        futures = [pool.submit(check, item) for item in payload["shards"]]
        for future in concurrent.futures.as_completed(futures):
            try:
                print("SANDIUM_SOURCE_SHARD_VERIFY=PASS " + future.result(), flush=True)
            except Exception as exc:
                errors.append(str(exc))
    if errors:
        fail("source shard verification failed: " + "; ".join(errors))
    print("SANDIUM_SOURCE_VERIFY=PASS ready=%s shards=%d" %
          (payload.get("ready"), len(payload["shards"])), flush=True)
    return payload


def restore(root: Path, workers: int, require_ready: bool) -> dict[str, Any]:
    payload = verify(root, workers, zstd_test=False, require_ready=require_ready)
    shard_dir = root / SHARDS_NAME
    errors: list[str] = []

    def extract(item: dict[str, Any]) -> str:
        archive = shard_dir / item["name"]
        cmd = ["tar", "-x", "-f", str(archive), "-I", "zstd -T1 -d", "-C", str(root)]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if proc.returncode:
            raise RuntimeError("source shard extraction failed %s: %s" %
                               (archive.name, proc.stderr.decode("utf-8", "replace")[-2000:]))
        return archive.name

    print("SANDIUM_SOURCE_RESTORE=START shards=%d workers=%d" %
          (len(payload["shards"]), min(workers, len(payload["shards"]))), flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(workers, len(payload["shards"]))) as pool:
        futures = [pool.submit(extract, item) for item in payload["shards"]]
        for future in concurrent.futures.as_completed(futures):
            try:
                print("SANDIUM_SOURCE_SHARD_RESTORE=PASS " + future.result(), flush=True)
            except Exception as exc:
                errors.append(str(exc))
    if errors:
        fail("source restore failed: " + "; ".join(errors))
    print("SANDIUM_SOURCE_RESTORE=PASS ready=%s" % payload.get("ready"), flush=True)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("archive", "verify", "restore"))
    parser.add_argument("--root", required=True)
    parser.add_argument("--workers", type=int, default=WORKERS_MAX)
    parser.add_argument("--stage", type=int, default=0)
    parser.add_argument("--ready", action="store_true")
    parser.add_argument("--zstd-test", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    workers = max(1, min(WORKERS_MAX, int(args.workers)))
    if not shutil.which("zstd") or not shutil.which("tar"):
        fail("tar and zstd are required")
    if args.command == "archive":
        archive(root, workers, args.stage, args.ready)
    elif args.command == "verify":
        verify(root, workers, args.zstd_test, args.ready)
    elif args.command == "restore":
        restore(root, workers, args.ready)


if __name__ == "__main__":
    main()
