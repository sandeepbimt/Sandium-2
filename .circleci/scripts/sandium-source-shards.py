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

SCHEMA = 2
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


def git_repository_state(repo: Path) -> dict[str, Any]:
    """Small, content-addressed summary of Git progress suitable for handover decisions.

    Pack names are content-derived by Git; sizes and timestamps also expose
    unfinished tmp_pack files. This does not read every blob or hash multi-GB
    packfiles. The enclosing checkpoint shard SHA256 protects the bytes.
    """
    head = subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
    ).strip()
    git_dir_text = subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "--absolute-git-dir"], text=True
    ).strip()
    git_dir = Path(git_dir_text)
    count_text = subprocess.check_output(
        ["git", "-C", str(repo), "count-objects", "-v"], text=True
    )
    counts: dict[str, str] = {}
    for line in count_text.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            counts[key.strip()] = value.strip()
    pack_dir = git_dir / "objects" / "pack"
    packfiles: list[dict[str, Any]] = []
    if pack_dir.is_dir():
        for item in sorted(pack_dir.iterdir(), key=lambda path: os.fsencode(path.name)):
            if not item.is_file():
                continue
            stat_result = item.stat()
            packfiles.append({
                "name": item.name,
                "size_bytes": stat_result.st_size,
                "mtime_ns": stat_result.st_mtime_ns,
            })
    shallow = (git_dir / "shallow").is_file()
    return {
        "head": head,
        "git_dir": str(git_dir.relative_to(repo)) if git_dir.is_relative_to(repo) else ".git",
        "shallow": shallow,
        "counts": counts,
        "packfiles": packfiles,
        "pack_file_count": sum(1 for item in packfiles if item["name"].endswith(".pack")),
        "pack_bytes": sum(item["size_bytes"] for item in packfiles if item["name"].endswith(".pack")),
        "temporary_pack_bytes": sum(item["size_bytes"] for item in packfiles if item["name"].startswith("tmp_pack_")),
    }


def file_state(path: Path, work: Path) -> dict[str, Any]:
    try:
        info = path.stat(follow_symlinks=False)
    except FileNotFoundError:
        return {"path": path.relative_to(work).as_posix(), "exists": False}
    return {
        "path": path.relative_to(work).as_posix(),
        "exists": True,
        "type": "symlink" if path.is_symlink() else ("directory" if path.is_dir() else "file"),
        "size_bytes": info.st_size,
        "mtime_ns": info.st_mtime_ns,
        "mode": stat.S_IMODE(info.st_mode),
    }


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
    actual_brave_sha = subprocess.check_output(
        ["git", "-C", str(core), "rev-parse", "HEAD"], text=True
    ).strip()
    if actual_brave != pins.get("BRAVE_CORE_TAG"):
        fail("Brave tag does not match source-pins.env")
    if pins.get("BRAVE_CORE_SHA") and actual_brave_sha != pins.get("BRAVE_CORE_SHA"):
        fail("Brave commit SHA does not match source-pins.env")
    if ready and actual_chromium != pins.get("CHROMIUM_SHA"):
        fail("ready Chromium SHA does not match source-pins.env")
    if ready and (not progress.get("REFRESH_REQUEST_ID") or
                  pins.get("REFRESH_REQUEST_ID") != progress.get("REFRESH_REQUEST_ID")):
        fail("ready source pins do not belong to the current refresh request")

    package = core / "package.json"
    try:
        package_data = json.loads(package.read_text(encoding="utf-8"))
        package_chromium_tag = package_data["config"]["projects"]["chrome"]["tag"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        fail("cannot read Brave package Chromium pin from package.json: %s" % exc)
    if pins.get("CHROMIUM_TAG") != package_chromium_tag:
        fail("source-pins Chromium tag differs from Brave package.json")
    if ready:
        import re
        if not re.fullmatch(r"v[0-9]+[.][0-9]+[.][0-9]+", actual_brave):
            fail("ready Brave pin is not a stable semantic-version tag: %s" % actual_brave)
        if not re.fullmatch(r"[0-9]+[.][0-9]+[.][0-9]+[.][0-9]+", package_chromium_tag):
            fail("ready Chromium pin is not a four-part version: %s" % package_chromium_tag)
        if len(pins.get("CHROMIUM_SHA", "")) != 40:
            fail("ready Chromium pin SHA is invalid")
        if len(actual_brave_sha) != 40:
            fail("ready Brave Core SHA is invalid")

    metadata: dict[str, Any] = {
        "source_prep_stage": stage,
        "source_prep_phase": progress.get("PHASE", "unknown"),
        "ready": ready,
        "brave_core_tag": actual_brave,
        "brave_core_sha": actual_brave_sha,
        "chromium_tag": pins.get("CHROMIUM_TAG", ""),
        "chromium_tag_from_brave_package": package_chromium_tag,
        "chromium_sha": pins.get("CHROMIUM_SHA", ""),
        "actual_chromium_sha": actual_chromium,
        "refresh_request_id": progress.get("REFRESH_REQUEST_ID", ""),
        "pin_refresh_request_id": pins.get("REFRESH_REQUEST_ID", ""),
        "gclient_sha256": sha256_file(work / ".gclient"),
        "gclient_entries_sha256": sha256_file(work / ".gclient_entries"),
        "source_pins_sha256": sha256_file(work / PINS_NAME),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    lockfile = core / "pnpm-lock.yaml"
    npmrc = core / ".npmrc"
    dep_files = [p for p in [package, lockfile, npmrc] if p.is_file()]
    dep_fingerprint = hashlib.sha256(
        "".join(sha256_file(p) for p in dep_files).encode("ascii")
    ).hexdigest()
    metadata["brave_dependency_fingerprint"] = dep_fingerprint

    chromium_git_state = git_repository_state(src)
    brave_git_state = git_repository_state(core)
    metadata["git_state"] = {
        "chromium": chromium_git_state,
        "brave_core": brave_git_state,
    }
    print(
        "SANDIUM_GIT_STATE repo=chromium head=%s shallow=%s packs=%d pack_bytes=%d loose_objects=%s temp_pack_bytes=%d"
        % (
            chromium_git_state["head"],
            chromium_git_state["shallow"],
            chromium_git_state["pack_file_count"],
            chromium_git_state["pack_bytes"],
            chromium_git_state["counts"].get("count", "unknown"),
            chromium_git_state["temporary_pack_bytes"],
        ),
        flush=True,
    )
    print(
        "SANDIUM_GIT_STATE repo=brave-core head=%s shallow=%s packs=%d pack_bytes=%d loose_objects=%s temp_pack_bytes=%d"
        % (
            brave_git_state["head"],
            brave_git_state["shallow"],
            brave_git_state["pack_file_count"],
            brave_git_state["pack_bytes"],
            brave_git_state["counts"].get("count", "unknown"),
            brave_git_state["temporary_pack_bytes"],
        ),
        flush=True,
    )

    phase_markers = {
        marker: (work / ".sandium" / marker).is_file()
        for marker in (
            "source-sync-complete",
            "source-runhooks-complete",
            "source-configure-complete",
            "source-gn-complete",
        )
    }
    out = src / "out" / "android_Release_arm64"
    critical_paths = [
        work / ".gclient",
        work / ".gclient_entries",
        work / PINS_NAME,
        package,
        lockfile,
        npmrc,
        core / ".env",
        out / "build.ninja",
        out / "args.gn",
        out / "args_generated.gni",
        src / "build" / "config" / "siso" / ".sisoenv",
        src / "build" / "config" / "siso" / ".sisorc",
        src / "build" / "config" / "siso" / "backend_config" / "backend.star",
        src / "build" / "config" / "siso" / "brave_siso_config.star",
        src / "buildtools" / "reclient_cfgs" / "python" / "python_remote_wrapper",
    ]
    fingerprint_payload = {
        "brave_core_tag": actual_brave,
        "brave_core_sha": actual_brave_sha,
        "chromium_tag": package_chromium_tag,
        "chromium_sha": pins.get("CHROMIUM_SHA", ""),
        "refresh_request_id": progress.get("REFRESH_REQUEST_ID", ""),
        "gclient_sha256": metadata["gclient_sha256"],
        "gclient_entries_sha256": metadata["gclient_entries_sha256"],
        "source_pins_sha256": metadata["source_pins_sha256"],
        "brave_dependency_fingerprint": dep_fingerprint,
        "git_state": metadata["git_state"],
        "phase_markers": phase_markers,
        "critical_files": [file_state(path, work) for path in critical_paths],
    }
    metadata["phase_markers"] = phase_markers
    metadata["critical_files"] = fingerprint_payload["critical_files"]
    metadata["source_state_fingerprint"] = hashlib.sha256(
        json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    if ready:
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


def archive(root: Path, workers: int, stage: int, ready: bool, skip_if_unchanged: bool = False) -> None:
    work = root / WORK_NAME
    progress_path = work / PROGRESS_NAME
    manifest_path = root / MANIFEST_NAME
    if not progress_path.is_file():
        fail("source preparation progress marker missing")
    roots, structural = discover_roots(root, work)
    metadata = source_metadata(root, work, stage, ready)
    unchanged_marker = work / ".sandium" / "source-archive-unchanged"
    unchanged_marker.unlink(missing_ok=True)
    if skip_if_unchanged and stage > 1 and not ready and manifest_path.is_file():
        try:
            previous, _previous_dir = load_manifest(root)
            previous_source = previous.get("source", {})
            same_state = (
                previous.get("ready") is False
                and previous_source.get("refresh_request_id") == metadata.get("refresh_request_id")
                and previous_source.get("source_state_fingerprint") == metadata.get("source_state_fingerprint")
            )
        except SystemExit:
            same_state = False
        if same_state:
            unchanged_marker.write_text(
                "UNCHANGED_SOURCE_STATE=true\nPARENT_MANIFEST_STAGE=%s\nSOURCE_STATE_FINGERPRINT=%s\n"
                % (previous.get("stage", "unknown"), metadata["source_state_fingerprint"]),
                encoding="utf-8",
            )
            print(
                "SANDIUM_SOURCE_ARCHIVE=REUSE unchanged=true parent_stage=%s fingerprint=%s; no new shards created"
                % (previous.get("stage", "unknown"), metadata["source_state_fingerprint"]),
                flush=True,
            )
            return
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
        import re
        source = payload.get("source", {})
        brave_tag = source.get("brave_core_tag", "")
        chromium_tag = source.get("chromium_tag", "")
        chromium_sha = source.get("chromium_sha", "")
        if not re.fullmatch(r"v[0-9]+[.][0-9]+[.][0-9]+", brave_tag):
            fail("source-ready Brave pin is not a stable version tag: %s" % brave_tag)
        if not re.fullmatch(r"[0-9]+[.][0-9]+[.][0-9]+[.][0-9]+", chromium_tag):
            fail("source-ready Chromium pin is not a four-part version: %s" % chromium_tag)
        if source.get("chromium_tag_from_brave_package") != chromium_tag:
            fail("source-ready Chromium tag does not match pinned Brave package.json")
        if source.get("actual_chromium_sha") != chromium_sha or not re.fullmatch(r"[0-9a-f]{40}", chromium_sha):
            fail("source-ready Chromium SHA is invalid or differs from actual checkout")
        if source.get("pin_refresh_request_id") != source.get("refresh_request_id") or not source.get("refresh_request_id"):
            fail("source-ready pin metadata is not bound to the current refresh request")
        if source.get("brave_core_sha") == "" or not re.fullmatch(r"[0-9a-f]{40}", source.get("brave_core_sha", "")):
            fail("source-ready Brave Core SHA is invalid")

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
        cmd = ["tar", "-x", "-I", "zstd -T1 -d", "-f", str(archive), "-C", str(root)]
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
    validate_restored_workspace(root, payload)
    print("SANDIUM_SOURCE_RESTORE=PASS ready=%s" % payload.get("ready"), flush=True)
    return payload


def validate_restored_workspace(root: Path, payload: dict[str, Any]) -> None:
    """Validate extracted source and repair only manifest-proven pin metadata."""
    work = root / WORK_NAME
    state = work / ".sandium"
    src = work / "src"
    core = src / "brave"
    source = payload.get("source", {})
    request_id = str(source.get("refresh_request_id", "")).strip()
    pin_request_id = str(source.get("pin_refresh_request_id", "")).strip()
    if not request_id:
        fail("restored source manifest has no refresh_request_id")
    if pin_request_id and pin_request_id != request_id:
        fail("restored source manifest pin and progress request IDs disagree")

    required = [
        work / ".gclient", work / ".gclient_entries",
        src / ".git", core / ".git",
        src / "build" / "install-build-deps.sh", src / "third_party",
        core / "package.json", core / "pnpm-lock.yaml",
        core / "node_modules" / ".modules.yaml", core / "node_modules" / ".pnpm",
    ]
    for path in required:
        if not path.exists():
            fail("restored source workspace is missing required component: %s" % path)

    for path, key in [
        (work / ".gclient", "gclient_sha256"),
        (work / ".gclient_entries", "gclient_entries_sha256"),
    ]:
        expected = source.get(key, "")
        if expected and sha256_file(path) != expected:
            fail("restored source metadata checksum mismatch: %s" % path)

    actual_chromium = subprocess.check_output(
        ["git", "-C", str(src), "rev-parse", "HEAD"], text=True
    ).strip()
    actual_brave_tag = subprocess.check_output(
        ["git", "-C", str(core), "describe", "--tags", "--exact-match"], text=True
    ).strip()
    actual_brave_sha = subprocess.check_output(
        ["git", "-C", str(core), "rev-parse", "HEAD"], text=True
    ).strip()
    if source.get("actual_chromium_sha") and actual_chromium != source["actual_chromium_sha"]:
        fail("restored Chromium HEAD differs from the checkpoint manifest")
    if actual_brave_tag != source.get("brave_core_tag"):
        fail("restored Brave tag differs from the checkpoint manifest")
    if source.get("brave_core_sha") and actual_brave_sha != source["brave_core_sha"]:
        fail("restored Brave SHA differs from the checkpoint manifest")

    package_data = json.loads((core / "package.json").read_text(encoding="utf-8"))
    package_chromium_tag = package_data["config"]["projects"]["chrome"]["tag"]
    if package_chromium_tag != source.get("chromium_tag"):
        fail("restored Brave package Chromium tag differs from the checkpoint manifest")

    pins_path = state / "source-pins.env"
    canonical_pins = (
        "BRAVE_CORE_TAG=%s\n"
        "BRAVE_CORE_SHA=%s\n"
        "CHROMIUM_TAG=%s\n"
        "CHROMIUM_SHA=%s\n"
        "REFRESH_REQUEST_ID=%s\n"
    ) % (
        source.get("brave_core_tag", ""),
        source.get("brave_core_sha", ""),
        source.get("chromium_tag", ""),
        source.get("chromium_sha", ""),
        request_id,
    )
    legacy_pins = (
        "BRAVE_CORE_TAG=%s\nCHROMIUM_TAG=%s\nCHROMIUM_SHA=%s\n"
    ) % (
        source.get("brave_core_tag", ""),
        source.get("chromium_tag", ""),
        source.get("chromium_sha", ""),
    )
    expected_pins_sha = source.get("source_pins_sha256", "")
    canonical_sha = hashlib.sha256(canonical_pins.encode("utf-8")).hexdigest()
    legacy_sha = hashlib.sha256(legacy_pins.encode("utf-8")).hexdigest()

    rewrite_pins = False
    if pins_path.is_file():
        current_sha = sha256_file(pins_path)
        pins = parse_kv(pins_path)
        for key, expected in [
            ("BRAVE_CORE_TAG", source.get("brave_core_tag", "")),
            ("CHROMIUM_TAG", source.get("chromium_tag", "")),
            ("CHROMIUM_SHA", source.get("chromium_sha", "")),
        ]:
            if pins.get(key) != expected:
                fail("restored source-pins.env disagrees with manifest field %s" % key)
        if pins.get("BRAVE_CORE_SHA") and pins["BRAVE_CORE_SHA"] != source.get("brave_core_sha"):
            fail("restored source-pins.env Brave SHA disagrees with manifest")
        if pins.get("REFRESH_REQUEST_ID") and pins["REFRESH_REQUEST_ID"] != request_id:
            fail("restored source-pins.env request ID disagrees with manifest")
        if current_sha == expected_pins_sha:
            rewrite_pins = not pins.get("BRAVE_CORE_SHA") or not pins.get("REFRESH_REQUEST_ID")
        elif expected_pins_sha == legacy_sha:
            rewrite_pins = True
        else:
            fail("restored source-pins.env checksum is not represented by the manifest")
    else:
        if expected_pins_sha == canonical_sha or expected_pins_sha == legacy_sha:
            rewrite_pins = True
        else:
            fail("source-pins.env is missing and cannot be reconstructed from the manifest checksum")

    if rewrite_pins:
        state.mkdir(parents=True, exist_ok=True)
        temporary = pins_path.with_suffix(".env.tmp")
        temporary.write_text(canonical_pins, encoding="utf-8")
        os.replace(temporary, pins_path)
        print("SANDIUM_SOURCE_HANDOFF_METADATA=RECOVERED source-pins.env from verified manifest", flush=True)

    progress_path = work / PROGRESS_NAME
    if progress_path.is_file():
        lines = progress_path.read_text(encoding="utf-8").splitlines()
        lines = [line for line in lines if not line.startswith("REFRESH_REQUEST_ID=")]
    else:
        lines = [
            "STAGE=%s" % payload.get("stage", source.get("source_prep_stage", "unknown")),
            "PHASE=%s" % source.get("source_prep_phase", "pinning-incomplete"),
        ]
    lines.append("REFRESH_REQUEST_ID=%s" % request_id)
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_progress = progress_path.with_suffix(".txt.tmp")
    temporary_progress.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.replace(temporary_progress, progress_path)

    print(
        "SANDIUM_SOURCE_HANDOFF=PASS request=%s Brave=%s Chromium=%s actual_chromium_head=%s"
        % (request_id, actual_brave_tag, package_chromium_tag, actual_chromium),
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("archive", "verify", "restore"))
    parser.add_argument("--root", required=True)
    parser.add_argument("--workers", type=int, default=WORKERS_MAX)
    parser.add_argument("--stage", type=int, default=0)
    parser.add_argument("--ready", action="store_true")
    parser.add_argument("--zstd-test", action="store_true")
    parser.add_argument("--skip-if-unchanged", action="store_true",
                        help="reuse the verified previous progress archive when source state did not change")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    workers = max(1, min(WORKERS_MAX, int(args.workers)))
    if not shutil.which("zstd") or not shutil.which("tar"):
        fail("tar and zstd are required")
    if args.command == "archive":
        archive(root, workers, args.stage, args.ready, args.skip_if_unchanged)
    elif args.command == "verify":
        verify(root, workers, args.zstd_test, args.ready)
    elif args.command == "restore":
        restore(root, workers, args.ready)


if __name__ == "__main__":
    main()
