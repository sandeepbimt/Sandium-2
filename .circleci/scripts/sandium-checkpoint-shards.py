#!/usr/bin/env python3
"""Parallel, independently verifiable Sandium workspace checkpoint shards.

The archive is partitioned by disjoint directory roots. Every shard is an
independent tar+zstd stream, so archive creation and extraction can each use up
to eight concurrent workers without concurrent writes to the same files.
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

SCHEMA_VERSION = 2
DEFAULT_WORKERS = 8
MAX_WORKERS = 8
WORK_NAME = "brave-work"
SHARD_DIR_NAME = "brave-workspace-checkpoint.shards"
MANIFEST_NAME = "brave-workspace-checkpoint.manifest.json"
OUTPUT_NAME = "android_Release_arm64"


def fail(message: str) -> "NoReturn":
    print("SANDIUM_CHECKPOINT_SHARDS=FAIL " + message, file=sys.stderr)
    raise SystemExit(1)


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def run_du(paths: list[Path]) -> dict[str, int]:
    if not paths:
        return {}
    command = ["du", "-sb", "--null", "--", *(str(path) for path in paths)]
    proc = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        fail("du could not measure archive candidates: " +
             proc.stderr.decode("utf-8", "replace")[-2000:])
    sizes: dict[str, int] = {}
    for record in proc.stdout.split(b"\0"):
        if not record:
            continue
        try:
            amount, raw_path = record.split(b"\t", 1)
            sizes[os.fsdecode(raw_path)] = int(amount)
        except (ValueError, TypeError):
            fail("could not parse du output while balancing shards")
    missing = [str(path) for path in paths if str(path) not in sizes]
    if missing:
        fail("du omitted candidate paths: " + ", ".join(missing[:5]))
    return sizes


def children(path: Path) -> list[Path]:
    try:
        return sorted(path.iterdir(), key=lambda item: os.fsencode(item.name))
    except OSError as exc:
        fail("cannot enumerate %s: %s" % (path, exc))


def discover_candidates(root: Path, work: Path) -> tuple[list[Path], list[Path]]:
    """Create non-overlapping roots, splitting src/out into useful components."""
    if not work.is_dir():
        fail("workspace directory is missing: %s" % work)
    src = work / "src"
    if not src.is_dir():
        fail("source directory is missing: %s" % src)
    out = src / "out"
    output = out / OUTPUT_NAME
    if not output.is_dir():
        fail("pinned output directory is missing: %s" % output)

    candidates: list[Path] = []
    structural = [work, src, out, output]

    # Small workspace-level data (for example .gclient and .sandium).
    for item in children(work):
        if item == src:
            continue
        candidates.append(item)

    # Chromium source components, with the large output tree split one level
    # deeper so that obj/gen/toolchain cannot become one oversized shard.
    for item in children(src):
        if item == out:
            continue
        candidates.append(item)

    for item in children(out):
        if item == output:
            continue
        candidates.append(item)

    for item in children(output):
        candidates.append(item)

    # A valid workspace must contain the checkpoint metadata and build graph.
    required = [
        work / ".gclient",
        work / ".sandium" / "action-ledger.json",
        src / ".git",
        src / "brave" / ".git",
        output / "build.ninja",
        output / "args.gn",
    ]
    for item in required:
        if not item.exists():
            fail("required workspace component is missing: %s" % item)

    if not candidates:
        fail("workspace produced no shard candidates")

    # Candidate roots must be unique and non-overlapping.
    rels = sorted(path.relative_to(root).as_posix() for path in candidates)
    for previous, current in zip(rels, rels[1:]):
        if current == previous or current.startswith(previous.rstrip("/") + "/"):
            fail("candidate ownership overlaps: %s and %s" % (previous, current))
    return candidates, structural


def expand_heavy_candidates(root: Path, candidates: list[Path],
                            workers: int) -> tuple[list[Path], dict[str, int]]:
    """Recursively split oversized directories before assigning workers."""
    current = list(candidates)
    depths = {str(path): 0 for path in current}
    final_sizes: dict[str, int] = {}

    for _pass in range(6):
        measured = run_du(current)
        total = sum(measured.values())
        target = max(1, int((total / max(1, workers)) * 1.20))
        replacements: dict[str, list[Path]] = {}
        for path in current:
            size = measured[str(path)]
            try:
                is_real_directory = stat.S_ISDIR(os.lstat(path).st_mode)
            except OSError:
                is_real_directory = False
            depth = depths.get(str(path), 0)
            if is_real_directory and size > target and depth < 5:
                nested = children(path)
                if len(nested) >= 2:
                    replacements[str(path)] = nested

        if not replacements:
            final_sizes = measured
            break

        next_candidates: list[Path] = []
        next_depths: dict[str, int] = {}
        for path in current:
            nested = replacements.get(str(path))
            if nested is None:
                next_candidates.append(path)
                next_depths[str(path)] = depths.get(str(path), 0)
                continue
            for child in nested:
                next_candidates.append(child)
                next_depths[str(child)] = depths.get(str(path), 0) + 1
        current = next_candidates
        depths = next_depths
        final_sizes = run_du(current)

    # Recalculate once after the last expansion pass; sizes are non-overlapping.
    final_sizes = run_du(current)
    total = sum(final_sizes.values())
    largest = max(final_sizes.values(), default=0)
    target = max(1, int((total / max(1, workers)) * 1.20))
    print("SANDIUM_SHARD_PLAN=PASS candidates=%d source_bytes=%d target_shard_bytes=%d largest_candidate_bytes=%d" %
          (len(current), total, target, largest))
    if largest > target:
        print("SANDIUM_SHARD_BALANCE=WARNING largest indivisible candidate exceeds target; recursive split depth or directory structure limited further splitting.")
    return current, final_sizes


def assign_buckets(candidates: list[Path], sizes: dict[str, int],
                   workers: int) -> list[list[Path]]:
    active = min(workers, len(candidates))
    buckets: list[list[Path]] = [[] for _ in range(active)]
    bucket_sizes = [0] * active
    ordered = sorted(candidates, key=lambda path: (-sizes[str(path)], os.fsencode(str(path))))
    for path in ordered:
        slot = min(range(active), key=lambda index: bucket_sizes[index])
        buckets[slot].append(path)
        bucket_sizes[slot] += sizes[str(path)]
    for bucket in buckets:
        bucket.sort(key=lambda path: os.fsencode(str(path)))
    if len(buckets) > 1:
        print("SANDIUM_SHARD_BALANCE=PASS workers=%d estimated_bucket_bytes=%s" %
              (active, ",".join(str(value) for value in bucket_sizes)))
    return buckets


def directory_metadata(root: Path, candidates: list[Path],
                       structural: list[Path]) -> list[dict[str, Any]]:
    parents: set[Path] = set(structural)
    for candidate in candidates:
        parent = candidate.parent
        while parent != root and root in parent.parents:
            parents.add(parent)
            parent = parent.parent
    records: list[dict[str, Any]] = []
    for path in sorted(parents, key=lambda item: (len(item.parts), os.fsencode(str(item)))):
        if not path.is_dir():
            continue
        info = os.stat(path, follow_symlinks=False)
        records.append({
            "path": path.relative_to(root).as_posix(),
            "mode": stat.S_IMODE(info.st_mode),
            "mtime_ns": info.st_mtime_ns,
        })
    return records


def parse_checkpoint_manifest(path: Path) -> dict[str, str]:
    if not path.is_file():
        fail("checkpoint manifest is missing: %s" % path)
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key] = value
    return result






def directory_inventory(root: Path) -> dict[str, tuple[int, int, int, int]]:
    """Fingerprint every directory entry point that can gain/lose children."""
    inventory: dict[str, tuple[int, int, int, int]] = {}
    for directory, _subdirs, _files in os.walk(root, followlinks=False):
        path = Path(directory)
        info = os.stat(path, follow_symlinks=False)
        relative = "." if path == root else path.relative_to(root).as_posix()
        inventory[relative] = (
            info.st_dev, info.st_ino, info.st_mtime_ns, info.st_ctime_ns
        )
    return inventory


def find_open_writers(work: Path) -> list[dict[str, str]]:
    """Find processes holding writable file descriptors anywhere in brave-work."""
    target_root = str(work.resolve())
    writers: list[dict[str, str]] = []
    proc_root = Path("/proc")
    if not proc_root.is_dir():
        raise RuntimeError("/proc is unavailable; cannot prove workspace quiescence")

    for process in proc_root.iterdir():
        if not process.name.isdigit():
            continue
        fd_dir = process / "fd"
        fdinfo_dir = process / "fdinfo"
        try:
            command = (process / "cmdline").read_bytes().replace(b"\0", b" ").decode(
                "utf-8", "replace"
            ).strip()
        except OSError:
            command = "<unavailable>"
        try:
            descriptors = list(fd_dir.iterdir())
        except OSError:
            continue

        for descriptor in descriptors:
            try:
                target = os.readlink(descriptor)
            except OSError:
                continue
            if target.endswith(" (deleted)"):
                target = target[:-10]
            if not os.path.isabs(target):
                continue
            try:
                if os.path.commonpath((target_root, os.path.normpath(target))) != target_root:
                    continue
            except ValueError:
                continue

            try:
                info = (fdinfo_dir / descriptor.name).read_text(encoding="ascii")
            except OSError:
                continue
            flags_line = next(
                (line for line in info.splitlines() if line.startswith("flags:")),
                None,
            )
            if flags_line is None:
                continue
            try:
                flags = int(flags_line.split(":", 1)[1].strip(), 8)
            except ValueError:
                continue
            if (flags & os.O_ACCMODE) == os.O_RDONLY:
                continue

            writers.append({
                "pid": process.name,
                "command": command[:240],
                "path": target,
            })
            break

    return writers


def create_hardlink_snapshot(
    work: Path,
    snapshot_work: Path,
    attempts: int = 3,
) -> dict[str, Any]:
    """Create a stable, same-filesystem namespace snapshot without copying file data.

    Directories are recreated, regular files are hard-linked, symlinks are
    copied as symlinks, and Ninja *.staging files are excluded. A before/after
    directory inventory plus writable-FD scans rejects any source-tree
    mutation detected during snapshot creation.
    """
    work = work.resolve()
    snapshot_work = snapshot_work.resolve()
    if snapshot_work == work or work in snapshot_work.parents:
        raise RuntimeError("snapshot destination must be outside the source workspace")

    last_reason = "workspace did not become quiescent"
    for attempt in range(1, attempts + 1):
        active_before = find_open_writers(work)
        if active_before:
            last_reason = "open writable descriptors before snapshot: %s" % active_before[:5]
            print(
                "SANDIUM_ARCHIVE_QUIESCENCE=WAIT attempt=%d writers=%d examples=%s" %
                (attempt, len(active_before), active_before[:3]),
                flush=True,
            )
            time.sleep(5)
            continue

        before = directory_inventory(work)
        shutil.rmtree(snapshot_work, ignore_errors=True)
        snapshot_work.parent.mkdir(parents=True, exist_ok=True)
        counts = {"hardlinked_files": 0, "excluded_staging_files": 0}

        def ignore_staging(_directory: str, names: list[str]) -> list[str]:
            ignored = [name for name in names if name.endswith(".staging")]
            counts["excluded_staging_files"] += len(ignored)
            return ignored

        def hardlink_file(source: str, destination: str) -> str:
            os.link(source, destination, follow_symlinks=False)
            counts["hardlinked_files"] += 1
            return destination

        try:
            shutil.copytree(
                work,
                snapshot_work,
                symlinks=True,
                copy_function=hardlink_file,
                ignore=ignore_staging,
            )
        except OSError as exc:
            shutil.rmtree(snapshot_work, ignore_errors=True)
            if exc.errno in (getattr(os, "EXDEV", 18),):
                raise RuntimeError(
                    "same-filesystem hard-link snapshot is unavailable; "
                    "refusing a 68-GB data-copy fallback"
                ) from exc
            last_reason = "snapshot copy encountered %s: %s" % (type(exc).__name__, exc)
            print(
                "SANDIUM_ARCHIVE_SNAPSHOT_RETRY=START attempt=%d reason=%s" %
                (attempt, last_reason),
                flush=True,
            )
            time.sleep(3)
            continue
        except shutil.Error as exc:
            shutil.rmtree(snapshot_work, ignore_errors=True)
            last_reason = "workspace changed while hard-link snapshot was being created: %s" % exc
            print(
                "SANDIUM_ARCHIVE_SNAPSHOT_RETRY=START attempt=%d reason=%s" %
                (attempt, last_reason),
                flush=True,
            )
            time.sleep(3)
            continue

        after = directory_inventory(work)
        active_after = find_open_writers(work)
        if before == after and not active_after:
            snapshot_directories = directory_inventory(snapshot_work)
            result = {
                "method": "same-filesystem-hardlink-directory-snapshot",
                "inventory_stable": True,
                "source_directory_count": len(before),
                "snapshot_directory_count": len(snapshot_directories),
                "hardlinked_files": counts["hardlinked_files"],
                "excluded_staging_files": counts["excluded_staging_files"],
                "quiescence_writable_fds_before": 0,
                "quiescence_writable_fds_after": 0,
                "snapshot_attempt": attempt,
            }
            print(
                "SANDIUM_ARCHIVE_SNAPSHOT=PASS method=hardlink "
                "directories=%d hardlinked_files=%d excluded_staging=%d attempt=%d" %
                (len(before), counts["hardlinked_files"],
                 counts["excluded_staging_files"], attempt),
                flush=True,
            )
            return result

        last_reason = (
            "source directory inventory changed=%s writable_descriptors_after=%d" %
            (before != after, len(active_after))
        )
        shutil.rmtree(snapshot_work, ignore_errors=True)
        print(
            "SANDIUM_ARCHIVE_SNAPSHOT_RETRY=START attempt=%d reason=%s examples=%s" %
            (attempt, last_reason, active_after[:3]),
            flush=True,
        )
        time.sleep(3)

    raise RuntimeError(
        "workspace did not reach a stable snapshot after %d attempt(s): %s" %
        (attempts, last_reason)
    )

def archive_worker(index: int, total: int, roots: list[Path],
                   source_root: Path, stage_dir: Path) -> dict[str, Any]:
    name = "shard-%02d-of-%02d.tar.zst" % (index, total)
    destination = stage_dir / name
    temporary = stage_dir / (name + ".tmp")
    list_file = stage_dir / (name + ".roots0")
    with list_file.open("wb") as stream:
        for path in roots:
            stream.write(os.fsencode(path.relative_to(source_root).as_posix()) + b"\0")

    tar_command = [
        "tar", "-c",
        "--format=posix",
        "--pax-option=delete=atime,delete=ctime",
        # Temporary Ninja outputs are not part of a stable handoff.
        "--exclude=*.staging",
        "--checkpoint=100000",
        "--checkpoint-action=echo=SHARD_%02d_TAR_CHECKPOINT=%%u" % index,
        "-C", str(source_root), "--null", "-T", str(list_file),
    ]
    zstd_command = ["zstd", "-T1", "--fast=5", "-q", "-o", str(temporary)]
    started = time.monotonic()
    tar_rc = -1
    zstd_rc = -1
    tar_diagnostic = ""
    attempts = 0

    # GNU tar returns 1 when files change while being read. This is not a
    # successful snapshot: retry once after the build/checkpoint has settled.
    # Keep the diagnostic enabled so repeated mutations are visible in CircleCI.
    for attempts in range(1, 3):
        temporary.unlink(missing_ok=True)
        with tempfile.TemporaryFile() as tar_stderr:
            tar = subprocess.Popen(tar_command, stdout=subprocess.PIPE, stderr=tar_stderr)
            assert tar.stdout is not None
            zstd = subprocess.Popen(zstd_command, stdin=tar.stdout, stdout=subprocess.DEVNULL)
            tar.stdout.close()
            zstd_rc = zstd.wait()
            tar_rc = tar.wait()
            tar_stderr.seek(0)
            tar_diagnostic = tar_stderr.read().decode("utf-8", "replace").strip()

        # Preserve the useful 100k-file progress markers while also surfacing
        # tar warnings that were previously hidden by --warning=no-file-changed.
        for line in tar_diagnostic.splitlines():
            if "SHARD_%02d_TAR_CHECKPOINT=" % index in line:
                print(line, flush=True)
            elif line:
                print("SANDIUM_TAR_DIAGNOSTIC shard=%02d %s" % (index, line),
                      file=sys.stderr, flush=True)

        # tar reads an immutable directory namespace; do not suppress read/change warnings.
        valid_output = temporary.is_file() and temporary.stat().st_size > 0
        if tar_rc == 0 and zstd_rc == 0 and valid_output:
            break

        if tar_rc == 1 and zstd_rc == 0 and attempts == 1:
            print(
                "SANDIUM_SHARD_ARCHIVE_RETRY=START shard=%02d reason=tar_exit_1 "
                "detail=%s" % (index, tar_diagnostic[-1000:] or "no tar diagnostic"),
                flush=True,
            )
            time.sleep(2)
            continue
        break

    list_file.unlink(missing_ok=True)
    elapsed = time.monotonic() - started
    if tar_rc != 0 or zstd_rc != 0 or not temporary.is_file() or temporary.stat().st_size == 0:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(
            "shard %02d failed after %d attempt(s): tar_exit=%d zstd_exit=%d tar_stderr=%s"
            % (index, attempts, tar_rc, zstd_rc, tar_diagnostic[-2000:] or "<empty>")
        )
    os.replace(temporary, destination)
    size_bytes = destination.stat().st_size
    return {
        "name": name,
        "size_bytes": size_bytes,
        "sha256": sha256_file(destination),
        "archive_seconds": round(elapsed, 3),
        "archive_attempts": attempts,
        "root_paths": [path.relative_to(source_root).as_posix() for path in roots],
    }


def archive(root: Path, workers: int) -> None:
    work = root / WORK_NAME
    shard_dir = root / SHARD_DIR_NAME
    manifest_path = root / MANIFEST_NAME
    manifest_path.unlink(missing_ok=True)
    stage_dir = root / (SHARD_DIR_NAME + ".tmp")
    shutil.rmtree(stage_dir, ignore_errors=True)
    stage_dir.mkdir(parents=True)

    snapshot_parent = Path(tempfile.mkdtemp(
        prefix=".sandium-archive-snapshot-", dir=str(root)
    ))
    snapshot_work = snapshot_parent / WORK_NAME
    try:
        snapshot_info = create_hardlink_snapshot(work, snapshot_work)
        candidates, structural = discover_candidates(snapshot_parent, snapshot_work)
        candidates, sizes = expand_heavy_candidates(snapshot_parent, candidates, workers)
        buckets = assign_buckets(candidates, sizes, workers)
        if not buckets:
            fail("no non-empty archive workers could be planned")
        dirs = directory_metadata(snapshot_parent, candidates, structural)
        checkpoint_file = snapshot_work / ".sandium" / "checkpoint-manifest.txt"
        checkpoint_manifest = parse_checkpoint_manifest(checkpoint_file)

        print("SANDIUM_PARALLEL_ARCHIVE=START workers=%d candidates=%d source_snapshot=hardlink" %
              (len(buckets), len(candidates)), flush=True)
        results: list[dict[str, Any]] = []
        errors: list[str] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(buckets)) as pool:
            futures = {
                pool.submit(
                    archive_worker, index, len(buckets), bucket,
                    snapshot_parent, stage_dir
                ): index
                for index, bucket in enumerate(buckets, 1)
            }
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                    print(
                        "SANDIUM_SHARD_ARCHIVE=PASS name=%s bytes=%d seconds=%.1f "
                        "attempts=%d roots=%d sha256=%s" %
                        (result["name"], result["size_bytes"], result["archive_seconds"],
                         result["archive_attempts"], len(result["root_paths"]),
                         result["sha256"]),
                        flush=True,
                    )
                except Exception as exc:
                    errors.append(str(exc))
                    print("SANDIUM_SHARD_ARCHIVE=FAIL " + str(exc), file=sys.stderr)

        if errors:
            shutil.rmtree(stage_dir, ignore_errors=True)
            fail(
                "parallel archive failed; no manifest will be published: " +
                "; ".join(errors)
            )

        # The source namespace is immutable now. Publish the full shard set and
        # manifest only after every strict tar+zstd worker and SHA pass succeeds.
        results.sort(key=lambda item: item["name"])
        shutil.rmtree(shard_dir, ignore_errors=True)
        os.replace(stage_dir, shard_dir)
        total_archive_bytes = sum(item["size_bytes"] for item in results)
        source_bytes = sum(sizes.values())
        largest_shard_bytes = max(item["size_bytes"] for item in results)
        average_shard_bytes = total_archive_bytes / len(results)
        shard_balance_ratio = round(largest_shard_bytes / max(1.0, average_shard_bytes), 3)
        payload = {
            "schema_version": SCHEMA_VERSION,
            "format": "independent-tar+zstd-shards",
            "workspace_root": WORK_NAME,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "workers": len(results),
            "max_workers": workers,
            "compression": "zstd --fast=5 -T1 per worker",
            "source_bytes": source_bytes,
            "archive_bytes": total_archive_bytes,
            "largest_shard_bytes": largest_shard_bytes,
            "average_shard_bytes": int(average_shard_bytes),
            "shard_balance_ratio": shard_balance_ratio,
            "excluded_transient_patterns": ["*.staging"],
            "source_snapshot": snapshot_info,
            "accepted_transient_read_race_count": 0,
            "directory_metadata": dirs,
            "checkpoint_manifest": checkpoint_manifest,
            "checkpoint_manifest_sha256": sha256_file(checkpoint_file),
            "shards": results,
        }
        temporary_manifest = manifest_path.with_suffix(manifest_path.suffix + ".tmp")
        temporary_manifest.write_text(
            json.dumps(payload, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary_manifest, manifest_path)
        print(
            "SANDIUM_PARALLEL_ARCHIVE=PASS workers=%d shards=%d source_bytes=%d "
            "archive_bytes=%d largest_shard_bytes=%d average_shard_bytes=%d "
            "balance_ratio=%s snapshot=hardlink" %
            (len(results), len(results), source_bytes, total_archive_bytes,
             largest_shard_bytes, int(average_shard_bytes), shard_balance_ratio),
            flush=True,
        )
        if shard_balance_ratio > 1.50:
            print(
                "SANDIUM_SHARD_BALANCE=WARNING largest compressed shard is %.2fx "
                "the average; inspect per-shard timings." % shard_balance_ratio,
                flush=True,
            )
    finally:
        shutil.rmtree(snapshot_parent, ignore_errors=True)

def load_manifest(root: Path) -> tuple[dict[str, Any], Path]:
    manifest_path = root / MANIFEST_NAME
    if not manifest_path.is_file():
        fail("shard manifest is missing: %s" % manifest_path)
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail("cannot read shard manifest: %s" % exc)
    if payload.get("schema_version") != SCHEMA_VERSION or payload.get("format") != "independent-tar+zstd-shards":
        fail("unsupported shard manifest schema/format")
    shard_dir = root / SHARD_DIR_NAME
    shards = payload.get("shards")
    if not isinstance(shards, list) or not shards or len(shards) > MAX_WORKERS:
        fail("manifest shard list is invalid")
    seen_roots: list[str] = []
    for item in shards:
        if not isinstance(item, dict) or not item.get("name"):
            fail("invalid shard record in manifest")
        name = item["name"]
        if Path(name).name != name:
            fail("unsafe shard filename in manifest: %r" % name)
        roots = item.get("root_paths")
        if not isinstance(roots, list) or not roots:
            fail("shard %s has no ownership roots" % name)
        for path in roots:
            if not isinstance(path, str) or Path(path).is_absolute() or ".." in Path(path).parts:
                fail("unsafe ownership path in shard %s" % name)
            if not (path == WORK_NAME or path.startswith(WORK_NAME + "/")):
                fail("shard path escapes workspace: %s" % path)
            for prior in seen_roots:
                if path == prior or path.startswith(prior.rstrip("/") + "/") or prior.startswith(path.rstrip("/") + "/"):
                    fail("overlapping shard ownership: %s and %s" % (path, prior))
            seen_roots.append(path)
    return payload, shard_dir


def verify(root: Path, zstd_test: bool, workers: int) -> dict[str, Any]:
    payload, shard_dir = load_manifest(root)
    shards = payload["shards"]

    def check(item: dict[str, Any]) -> str:
        path = shard_dir / item["name"]
        if not path.is_file():
            raise RuntimeError("missing shard %s" % path)
        actual_size = path.stat().st_size
        if actual_size != int(item["size_bytes"]):
            raise RuntimeError("size mismatch for %s expected=%s actual=%s" %
                               (path.name, item["size_bytes"], actual_size))
        actual_sha = sha256_file(path)
        if actual_sha != item["sha256"]:
            raise RuntimeError("SHA256 mismatch for %s" % path.name)
        if zstd_test:
            proc = subprocess.run(["zstd", "-t", str(path)], stdout=subprocess.DEVNULL,
                                  stderr=subprocess.PIPE)
            if proc.returncode != 0:
                raise RuntimeError("zstd integrity failure for %s: %s" %
                                   (path.name, proc.stderr.decode("utf-8", "replace")[-1000:]))
        return path.name

    errors: list[str] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(workers, len(shards))) as pool:
        futures = [pool.submit(check, item) for item in shards]
        for future in concurrent.futures.as_completed(futures):
            try:
                print("SANDIUM_SHARD_VERIFY=PASS " + future.result())
            except Exception as exc:
                errors.append(str(exc))
    if errors:
        fail("shard verification failed: " + "; ".join(errors))
    print("SANDIUM_SHARD_VERIFY=PASS shards=%d zstd_test=%s" % (len(shards), zstd_test))
    return payload


def restore(root: Path, workers: int) -> None:
    payload = verify(root, zstd_test=False, workers=workers)
    shard_dir = root / SHARD_DIR_NAME
    shards = payload["shards"]

    def extract(item: dict[str, Any]) -> str:
        archive_path = shard_dir / item["name"]
        command = [
            "tar", "-x",
            "-I", "zstd -T1 -d",
            "-f", str(archive_path),
            "-C", str(root),
        ]
        proc = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if proc.returncode != 0:
            raise RuntimeError("extraction failed for %s: %s" %
                               (archive_path.name, proc.stderr.decode("utf-8", "replace")[-2000:]))
        return archive_path.name

    errors: list[str] = []
    print("SANDIUM_PARALLEL_RESTORE=START workers=%d shards=%d" %
          (min(workers, len(shards)), len(shards)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(workers, len(shards))) as pool:
        futures = [pool.submit(extract, item) for item in shards]
        for future in concurrent.futures.as_completed(futures):
            try:
                print("SANDIUM_SHARD_RESTORE=PASS " + future.result())
            except Exception as exc:
                errors.append(str(exc))
                print("SANDIUM_SHARD_RESTORE=FAIL " + str(exc), file=sys.stderr)
    if errors:
        fail("parallel extraction failed: " + "; ".join(errors))

    # tar creates missing ancestors automatically. Restore their original
    # mode/mtime after all workers have finished writing beneath them.
    metadata = payload.get("directory_metadata", [])
    for item in sorted(metadata, key=lambda value: value["path"].count("/"), reverse=True):
        path = root / item["path"]
        if not path.is_dir():
            path.mkdir(parents=True, exist_ok=True)
        os.chmod(path, int(item["mode"]))
        stamp = int(item["mtime_ns"])
        os.utime(path, ns=(stamp, stamp))
    print("SANDIUM_PARALLEL_RESTORE=PASS shards=%d workers=%d" %
          (len(shards), min(workers, len(shards))))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("archive", "verify", "restore"))
    parser.add_argument("--root", required=True)
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--zstd-test", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    workers = max(1, min(MAX_WORKERS, int(args.workers)))
    if not shutil.which("zstd") or not shutil.which("tar"):
        fail("both zstd and tar must be installed")
    if args.command == "archive":
        archive(root, workers)
    elif args.command == "verify":
        verify(root, zstd_test=True, workers=workers)
    elif args.command == "restore":
        restore(root, workers)


if __name__ == "__main__":
    main()
