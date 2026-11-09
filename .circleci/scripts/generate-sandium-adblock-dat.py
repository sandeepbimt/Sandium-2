#!/usr/bin/env python3
"""Generate a genuine Brave 0.13.3 engine1.dat for Sandium's Android APK.

The artifact is generated under out/android_Release_arm64/gen so it follows
normal Full Mode workspace checkpoints and is packaged by Brave's Android
asset target. Raw third-party filter sources are not copied into the APK.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import runpy
import shutil
import subprocess
import sys
import time
import tomllib
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXPECTED_BRAVE_TAG = "v1.98.62"
EXPECTED_BRAVE_SHA = "44a84b1f89d9a35287289d6a3d493e362f5a5123"
EXPECTED_CHROMIUM_TAG = "156.0.8078.74"
EXPECTED_CHROMIUM_SHA = "d331de35ca8ab1358c7a17e4bd41627d55eaef51"
ADBLOCK_VERSION = "0.13.3"
EXPECTED_INCLUDED_SOURCES = 27
MAX_SOURCE_BYTES = 24 * 1024 * 1024
MAX_TOTAL_BYTES = 180 * 1024 * 1024
FRESH_SECONDS = 6 * 60 * 60
STALE_FALLBACK_SECONDS = 7 * 24 * 60 * 60
LICENSE_REFERENCE = "https://github.com/gorhill/uBlock/wiki/Filter-list-licenses"

# These two feeds remain enabled in Sandium's ordinary profile subscription
# system, but are deliberately not redistributed in the APK baseline because
# the published uBO license inventory identifies non-commercial terms.
NOT_BUNDLED_LICENSE_RESTRICTIONS = {
    "https://pgl.yoyo.org/adservers/serverlist.php?hostformat=hosts&showintro=1&mimetype=plaintext": {
        "reason": "McRae GPL terms are identified as non-commercial in the uBO license inventory",
        "license": "McRae GPL (non-commercial)",
        "reference": "https://pgl.yoyo.org/license/",
    },
    "https://someonewhocares.org/hosts/hosts": {
        "reason": "published terms are informal attribution and non-commercial",
        "license": "Informal attribution / non-commercial",
        "reference": "https://someonewhocares.org/hosts/",
    },
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp.replace(path)


def iso_utc(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat().replace("+00:00", "Z")


def verify_pin(core: Path, src: Path) -> None:
    def git(*args: str, cwd: Path) -> str:
        return subprocess.run(["git", *args], cwd=cwd, check=True,
                              capture_output=True, text=True).stdout.strip()

    brave_tag = git("describe", "--tags", "--exact-match", cwd=core)
    brave_sha = git("rev-parse", "HEAD", cwd=core)
    chromium_sha = git("rev-parse", "HEAD", cwd=src)
    package = json.loads((core / "package.json").read_text(encoding="utf-8"))
    chromium_tag = package["config"]["projects"]["chrome"]["tag"]
    expected = (EXPECTED_BRAVE_TAG, EXPECTED_BRAVE_SHA,
                EXPECTED_CHROMIUM_TAG, EXPECTED_CHROMIUM_SHA)
    actual = (brave_tag, brave_sha, chromium_tag, chromium_sha)
    if actual != expected:
        raise RuntimeError(f"pinned source mismatch: expected={expected} actual={actual}")
    print(f"SANDIUM_ADBLOCK_DAT_PIN=PASS brave={brave_tag}@{brave_sha} chromium={chromium_tag}@{chromium_sha}")


def filter_definitions(root: Path) -> list[tuple[str, str]]:
    script = root / ".circleci/scripts/apply-sandium-filter-subscriptions.py"
    module = runpy.run_path(str(script))
    return list(module["FILTERS"])


def license_for(url: str, title: str) -> tuple[str, str]:
    lower = url.lower()
    title_lower = title.lower()
    if "filters.adtidy.org" in lower:
        return "GPL-3.0", LICENSE_REFERENCE
    if "malware-filter.gitlab.io/urlhaus-filter" in lower:
        return "CC0-1.0", LICENSE_REFERENCE
    if "malware-filter.gitlab.io/phishing-filter" in lower:
        return "CC0-1.0", LICENSE_REFERENCE
    if "fanboy.co.nz/fanboy-antifacebook" in lower:
        return "CC-BY-3.0", LICENSE_REFERENCE
    if "indianlist.txt" in lower:
        return "GPL-3.0 OR CC-BY-SA-3.0", LICENSE_REFERENCE
    if "ublockorigin.github.io/uassets/thirdparties/easylist" in lower:
        return "GPL-3.0 OR CC-BY-SA-3.0", LICENSE_REFERENCE
    if "ublockorigin.github.io/uassets/thirdparties/easyprivacy" in lower:
        return "GPL-3.0 OR CC-BY-SA-3.0", LICENSE_REFERENCE
    if "ublockorigin.github.io/uassets/filters/" in lower:
        return "GPL-3.0", LICENSE_REFERENCE
    raise RuntimeError(f"no redistribution license mapping for selected filter: {title} ({url})")


def download_filter(url: str, target: Path, now: float) -> tuple[dict[str, Any], bool]:
    target.parent.mkdir(parents=True, exist_ok=True)
    metadata_path = target.with_suffix(target.suffix + ".http.json")
    old_meta: dict[str, Any] = {}
    if metadata_path.is_file():
        try:
            old_meta = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            old_meta = {}

    headers = {
        "User-Agent": "Sandium-Filter-Snapshot/1.0 (+https://github.com/sandeepbimt/Sandium-2)",
        "Accept": "text/plain,*/*;q=0.8",
    }
    if target.is_file() and old_meta.get("etag"):
        headers["If-None-Match"] = str(old_meta["etag"])
    if target.is_file() and old_meta.get("last_modified"):
        headers["If-Modified-Since"] = str(old_meta["last_modified"])

    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=35) as response:
            content = response.read(MAX_SOURCE_BYTES + 1)
            if len(content) > MAX_SOURCE_BYTES:
                raise RuntimeError(f"filter source exceeds {MAX_SOURCE_BYTES} bytes: {url}")
            etag = response.headers.get("ETag")
            modified = response.headers.get("Last-Modified")
            status = response.status
            if status != 200:
                raise RuntimeError(f"unexpected HTTP status {status} for {url}")
            if len(content) < 100:
                raise RuntimeError(f"filter source is unexpectedly short ({len(content)} bytes): {url}")
            content.decode("utf-8")
            temp = target.with_suffix(target.suffix + ".tmp")
            temp.write_bytes(content)
            temp.replace(target)
            old_meta = {
                "url": url,
                "etag": etag,
                "last_modified": modified,
                "fetched_at": now,
            }
            atomic_json(metadata_path, old_meta)
            return {"bytes": len(content), "sha256": sha256(content),
                    "fetched_at": now, "http_status": status}, True
    except urllib.error.HTTPError as error:
        if error.code == 304 and target.is_file():
            content = target.read_bytes()
            content.decode("utf-8")
            return {"bytes": len(content), "sha256": sha256(content),
                    "fetched_at": old_meta.get("fetched_at", now),
                    "http_status": 304}, False
        if target.is_file() and old_meta.get("fetched_at"):
            age = now - float(old_meta["fetched_at"])
            if age <= STALE_FALLBACK_SECONDS:
                content = target.read_bytes()
                if 100 <= len(content) <= MAX_SOURCE_BYTES:
                    content.decode("utf-8")
                    print(f"SANDIUM_FILTER_SOURCE_STALE_FALLBACK age_seconds={int(age)} url={url} http={error.code}")
                    return {"bytes": len(content), "sha256": sha256(content),
                            "fetched_at": old_meta["fetched_at"],
                            "http_status": f"stale-fallback-http-{error.code}"}, False
        raise RuntimeError(f"cannot fetch selected filter source {url}: HTTP {error.code}") from error
    except Exception as error:
        if target.is_file() and old_meta.get("fetched_at"):
            age = now - float(old_meta["fetched_at"])
            if age <= STALE_FALLBACK_SECONDS:
                content = target.read_bytes()
                if 100 <= len(content) <= MAX_SOURCE_BYTES:
                    content.decode("utf-8")
                    print(f"SANDIUM_FILTER_SOURCE_STALE_FALLBACK age_seconds={int(age)} url={url} error={error}")
                    return {"bytes": len(content), "sha256": sha256(content),
                            "fetched_at": old_meta["fetched_at"],
                            "http_status": "stale-fallback"}, False
        raise RuntimeError(f"cannot fetch selected filter source {url}: {error}") from error


def load_valid_snapshot(out_dir: Path, workflow_id: str, included_urls: list[str]) -> dict[str, Any] | None:
    manifest_path = out_dir / "snapshot.json"
    dat_path = out_dir / "engine1.dat"
    if not manifest_path.is_file() or not dat_path.is_file():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        sources_path = out_dir / "sources.json"
        if (manifest.get("brave_core_sha") != EXPECTED_BRAVE_SHA or
                manifest.get("chromium_sha") != EXPECTED_CHROMIUM_SHA or
                manifest.get("adblock_version") != ADBLOCK_VERSION or
                manifest.get("included_source_urls") != included_urls or
                manifest.get("included_source_count") != EXPECTED_INCLUDED_SOURCES or
                not sources_path.is_file() or
                sha256(sources_path.read_bytes()) != manifest.get("sources_json_sha256") or
                sha256(dat_path.read_bytes()) != manifest.get("engine1_dat_sha256")):
            return None
        source_doc = json.loads(sources_path.read_text(encoding="utf-8"))
        source_records = source_doc.get("sources", [])
        if len(source_records) != EXPECTED_INCLUDED_SOURCES:
            return None
        for record in source_records:
            source_file = out_dir / "lists" / f"filter-{int(record['index']):02d}.txt"
            if not source_file.is_file() or sha256(source_file.read_bytes()) != record.get("sha256"):
                return None
        age = time.time() - float(manifest.get("snapshot_created_at", 0))
        if manifest.get("circle_workflow_id") == workflow_id:
            print("SANDIUM_ADBLOCK_DAT_REUSE=PASS reason=same_workflow_checkpoint")
            return manifest
        if age <= FRESH_SECONDS:
            print(f"SANDIUM_ADBLOCK_DAT_REUSE=PASS reason=fresh_snapshot age_seconds={int(age)}")
            manifest["circle_workflow_id"] = workflow_id
            manifest["workflow_reuse"] = True
            atomic_json(manifest_path, manifest)
            return manifest
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None
    return None


def run_rust_generator(root: Path, src: Path, out_dir: Path, input_paths: list[Path]) -> dict[str, int]:
    toolchain_bin = src / "third_party/rust-toolchain/bin"
    env = os.environ.copy()
    env["PATH"] = str(toolchain_bin) + os.pathsep + env.get("PATH", "")
    cargo = shutil.which("cargo", path=env["PATH"])
    if not cargo:
        raise RuntimeError("pinned Chromium Rust toolchain cargo binary was not found")
    rustc = shutil.which("rustc", path=env["PATH"])
    if not rustc:
        raise RuntimeError("pinned Chromium Rust toolchain rustc binary was not found")
    print("SANDIUM_DAT_RUSTC=" + subprocess.run([rustc, "--version"], check=True,
                                               capture_output=True, text=True).stdout.strip())
    print("SANDIUM_DAT_CARGO=" + subprocess.run([cargo, "--version"], check=True,
                                                capture_output=True, text=True).stdout.strip())

    generator_source = root / ".circleci/scripts/sandium-adblock-datgen"
    # Brave keeps its Brave-specific crate sources (including adblock) under
    # src/brave, while Chromium's shared crates (for example base64) live under
    # src/third_party. The pinned Brave Cargo.lock spans both vendor trees.
    vendor = src / "brave/third_party/rust/chromium_crates_io/vendor"
    chromium_vendor = src / "third_party/rust/chromium_crates_io/vendor"
    vendor_lock = src / "brave/third_party/rust/chromium_crates_io/Cargo.lock"
    vendor_roots = [chromium_vendor, vendor]
    missing_roots = [str(path) for path in vendor_roots if not path.is_dir()]
    if missing_roots or not vendor_lock.is_file():
        raise RuntimeError(
            "pinned Brave/Chromium Rust vendor inputs are missing; "
            f"missing_vendor_roots={missing_roots} lockfile={vendor_lock} "
            f"lockfile_exists={vendor_lock.is_file()}"
        )

    work = out_dir / "generator-workspace"
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(generator_source, work)
    shutil.copy2(vendor_lock, work / "Cargo.lock")
    # Cargo directory sources need canonical "<crate>-<version>" package names.
    # Build one temporary view over both pinned vendor roots; do not mutate them.
    # Chromium is scanned first because Brave's Cargo.toml patches shared crates
    # to Chromium's copies. Brave-only packages such as adblock are added next.
    cargo_vendor = work / "cargo-vendor"
    cargo_vendor.mkdir(parents=True, exist_ok=True)
    aliases = 0
    discovered_adblock: dict[str, Path] = {}
    alias_targets: dict[str, tuple[Path, str | None]] = {}
    vendor_diagnostics: list[str] = []

    for vendor_root in vendor_roots:
        vendor_children = sorted(vendor_root.iterdir())
        vendor_diagnostics.append(
            f"{vendor_root}: children={len(vendor_children)} "
            f"sample={[p.name for p in vendor_children[:20]]}"
        )
        # Direct-child traversal is intentional: Chromium's GN vendor tree is
        # flat, and rglob does not reliably descend through directory symlinks.
        for crate_dir in vendor_children:
            if not crate_dir.is_dir():
                continue
            manifest_path = crate_dir / "Cargo.toml"
            checksum_path = crate_dir / ".cargo-checksum.json"
            if not manifest_path.is_file() or not checksum_path.is_file():
                continue
            package = tomllib.loads(manifest_path.read_text(encoding="utf-8")).get("package", {})
            name, version = package.get("name"), package.get("version")
            if not name or not version:
                continue
            alias_name = f"{name}-{version}"
            alias = cargo_vendor / alias_name
            resolved_crate = crate_dir.resolve()
            checksum = json.loads(checksum_path.read_text(encoding="utf-8"))
            package_checksum = checksum.get("package")

            if alias_name in alias_targets:
                previous_path, previous_checksum = alias_targets[alias_name]
                if previous_path == resolved_crate:
                    continue
                # Same registry package/version may be present in both trees.
                # Reuse the Chromium-first copy only when the crate archive
                # checksum proves both entries represent the same package.
                if package_checksum and package_checksum == previous_checksum:
                    continue
                raise RuntimeError(
                    "conflicting vendored copies for Cargo package "
                    f"{alias_name}: first={previous_path} second={resolved_crate} "
                    f"first_checksum={previous_checksum} second_checksum={package_checksum}"
                )

            alias.symlink_to(resolved_crate, target_is_directory=True)
            alias_targets[alias_name] = (resolved_crate, package_checksum)
            aliases += 1
            if name == "adblock" and version == "0.13.3":
                discovered_adblock[str(resolved_crate)] = resolved_crate

    expected_alias = cargo_vendor / "adblock-0.13.3"
    if len(discovered_adblock) != 1:
        raise RuntimeError(
            "expected exactly one pinned adblock 0.13.3 manifest across Brave and Chromium vendor trees; "
            f"found={len(discovered_adblock)} roots={' | '.join(vendor_diagnostics)}"
        )
    if not expected_alias.is_symlink() or not expected_alias.exists():
        expected_alias.symlink_to(next(iter(discovered_adblock.values())), target_is_directory=True)
    if not expected_alias.is_symlink() or not expected_alias.exists():
        raise RuntimeError(
            "failed to expose pinned adblock 0.13.3; "
            f"alias={expected_alias} roots={' | '.join(vendor_diagnostics)}"
        )
    required_aliases = ("adblock-0.13.3", "base64-0.22.1")
    missing_aliases = [name for name in required_aliases if not (cargo_vendor / name).is_symlink()]
    if missing_aliases:
        raise RuntimeError(
            "combined Cargo vendor view is incomplete; "
            f"missing_aliases={missing_aliases} roots={' | '.join(vendor_diagnostics)}"
        )
    print(
        f"SANDIUM_DAT_CARGO_VENDOR=PASS aliases={aliases} "
        "adblock=adblock-0.13.3 base64=base64-0.22.1 roots=2"
    )

    cargo_config = work / ".cargo/config.toml"
    cargo_config.parent.mkdir(parents=True, exist_ok=True)
    cargo_config.write_text(
        "[source.crates-io]\nreplace-with = 'brave-vendored-sources'\n\n"
        "[source.brave-vendored-sources]\n"
        f"directory = {json.dumps(str(cargo_vendor))}\n",
        encoding="utf-8",
    )

    target_dir = out_dir / "cargo-target"
    env["CARGO_TARGET_DIR"] = str(target_dir)
    dat_path = out_dir / "engine1.dat"
    command = [cargo, "run", "--offline", "--release", "--manifest-path",
               str(work / "Cargo.toml"), "--", str(dat_path)] + [str(p) for p in input_paths]
    print("SANDIUM_DAT_GENERATOR=START adblock=0.13.3 sources=27 cargo_offline=true")
    completed = subprocess.run(command, cwd=work, env=env, check=False,
                               text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    # Always preserve Cargo's compiler/runtime diagnostics in the CircleCI
    # step log. check=True raises CalledProcessError with captured output but
    # the traceback alone omits that output, hiding the actual failure.
    if completed.stdout:
        print(completed.stdout, end="", flush=True)
    if completed.returncode != 0:
        tail = "\\n".join(completed.stdout.splitlines()[-160:])
        raise RuntimeError(
            f"pinned Brave DAT generator failed (exit={completed.returncode}); "
            f"Cargo output follows:\\n{tail}"
        )
    stats: dict[str, int] = {}
    for line in completed.stdout.splitlines():
        if line.startswith("SANDIUM_DAT_") and "=" in line:
            key, value = line.split("=", 1)
            if value.isdigit():
                stats[key] = int(value)
    required = ("SANDIUM_DAT_SOURCE_COUNT", "SANDIUM_DAT_NETWORK_RULES",
                "SANDIUM_DAT_COSMETIC_RULES", "SANDIUM_DAT_BYTES")
    missing = [key for key in required if key not in stats]
    if missing:
        raise RuntimeError("Rust generator did not report metrics: " + ",".join(missing))
    if stats["SANDIUM_DAT_SOURCE_COUNT"] != EXPECTED_INCLUDED_SOURCES or stats["SANDIUM_DAT_NETWORK_RULES"] <= 0:
        raise RuntimeError(f"invalid generated DAT metrics: {stats}")
    if not dat_path.is_file() or dat_path.stat().st_size != stats["SANDIUM_DAT_BYTES"]:
        raise RuntimeError("generated DAT file size does not match Rust generator report")
    return stats


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--src", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    src = (args.src or (root / "brave-work/src")).resolve()
    core = src / "brave"
    out = (args.out or (src / "out/android_Release_arm64/gen/sandium_adblock")).resolve()
    workflow_id = os.environ.get("CIRCLE_WORKFLOW_ID", "local-validation")
    out.mkdir(parents=True, exist_ok=True)
    verify_pin(core, src)

    filters = filter_definitions(root)
    if len(filters) != 29 or len({url for url, _ in filters}) != 29:
        raise RuntimeError("the configured Sandium subscription catalogue must contain 29 unique entries")

    included: list[tuple[str, str, str, str]] = []
    excluded: list[dict[str, str]] = []
    for url, title in filters:
        if url in NOT_BUNDLED_LICENSE_RESTRICTIONS:
            excluded.append({"url": url, "title": title,
                             **NOT_BUNDLED_LICENSE_RESTRICTIONS[url]})
            continue
        license_name, license_ref = license_for(url, title)
        included.append((url, title, license_name, license_ref))
    if len(included) != EXPECTED_INCLUDED_SOURCES:
        raise RuntimeError(f"redistributable baseline catalogue changed: expected {EXPECTED_INCLUDED_SOURCES}, got {len(included)}")

    included_urls = [item[0] for item in included]
    existing = load_valid_snapshot(out, workflow_id, included_urls)
    if existing:
        dat_path = out / "engine1.dat"
        sources_path = out / "sources.json"
        if not sources_path.is_file() or sha256(sources_path.read_bytes()) != existing.get("sources_json_sha256"):
            raise RuntimeError("cached DAT snapshot metadata failed integrity validation")
        print(f"SANDIUM_ADBLOCK_DAT=REUSE bytes={dat_path.stat().st_size} sha256={existing['engine1_dat_sha256']}")
        return

    now = time.time()
    input_paths: list[Path] = []
    source_records: list[dict[str, Any]] = []
    total_bytes = 0
    source_dir = out / "lists"
    for index, (url, title, license_name, license_ref) in enumerate(included, 1):
        target = source_dir / f"filter-{index:02d}.txt"
        downloaded, changed = download_filter(url, target, now)
        content = target.read_bytes()
        total_bytes += len(content)
        if total_bytes > MAX_TOTAL_BYTES:
            raise RuntimeError(f"selected filter snapshot exceeds {MAX_TOTAL_BYTES} bytes")
        input_paths.append(target)
        source_records.append({
            "index": index,
            "title": title,
            "url": url,
            "license": license_name,
            "license_reference": license_ref,
            "sha256": downloaded["sha256"],
            "bytes": downloaded["bytes"],
            "last_source_fetch_utc": iso_utc(float(downloaded["fetched_at"])),
            "http_status": downloaded["http_status"],
            "changed_during_this_run": changed,
        })

    print(f"SANDIUM_FILTER_SNAPSHOT=PASS included={len(source_records)} excluded_noncommercial={len(excluded)} raw_bytes={total_bytes}")
    stats = run_rust_generator(root, src, out, input_paths)
    dat_path = out / "engine1.dat"
    dat_bytes = dat_path.read_bytes()
    dat_hash = sha256(dat_bytes)
    sources_doc = {
        "format": "Sandium bundled Brave adblock DAT source manifest v1",
        "brave_core": {"tag": EXPECTED_BRAVE_TAG, "sha": EXPECTED_BRAVE_SHA},
        "chromium": {"tag": EXPECTED_CHROMIUM_TAG, "sha": EXPECTED_CHROMIUM_SHA},
        "adblock_rust_version": ADBLOCK_VERSION,
        "selected_subscription_count": len(filters),
        "bundled_subscription_count": len(source_records),
        "excluded_from_bundled_snapshot": excluded,
        "sources": source_records,
        "engine": {
            "asset": "sandium/adblock/engine1.dat",
            "sha256": dat_hash,
            "bytes": len(dat_bytes),
            "network_filter_count": stats["SANDIUM_DAT_NETWORK_RULES"],
            "cosmetic_filter_count": stats["SANDIUM_DAT_COSMETIC_RULES"],
            "source_count": stats["SANDIUM_DAT_SOURCE_COUNT"],
            "roundtrip_deserialization": "passed using adblock 0.13.3",
        },
        "generated_utc": iso_utc(now),
        "circle_workflow_id": workflow_id,
        "notes": [
            "The DAT contains serialized network and cosmetic filter engine state.",
            "Brave loads scriptlet and redirect resources separately through its normal resource provider.",
            "Two non-commercial sources remain in the normal profile subscription catalogue but are not redistributed in this APK baseline.",
        ],
    }
    sources_bytes = (json.dumps(sources_doc, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    sources_path = out / "sources.json"
    temp = sources_path.with_suffix(".json.tmp")
    temp.write_bytes(sources_bytes)
    temp.replace(sources_path)

    manifest = {
        "brave_core_sha": EXPECTED_BRAVE_SHA,
        "chromium_sha": EXPECTED_CHROMIUM_SHA,
        "adblock_version": ADBLOCK_VERSION,
        "included_source_urls": included_urls,
        "included_source_count": len(source_records),
        "excluded_source_count": len(excluded),
        "snapshot_created_at": now,
        "circle_workflow_id": workflow_id,
        "engine1_dat_sha256": dat_hash,
        "engine1_dat_bytes": len(dat_bytes),
        "sources_json_sha256": sha256(sources_bytes),
        "stats": stats,
    }
    atomic_json(out / "snapshot.json", manifest)
    print(f"SANDIUM_ADBLOCK_DAT_GENERATION=PASS bytes={len(dat_bytes)} sha256={dat_hash} network_rules={stats['SANDIUM_DAT_NETWORK_RULES']} cosmetic_rules={stats['SANDIUM_DAT_COSMETIC_RULES']}")
    print(f"SANDIUM_ADBLOCK_DAT_ASSETS=PASS engine={dat_path} sources={sources_path}")
    print("SANDIUM_ADBLOCK_LICENSE_GATE=PASS bundled=27 skipped_noncommercial=2 attribution_manifest=sources.json")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"SANDIUM_ADBLOCK_DAT_GENERATION=FAIL {error}", file=sys.stderr)
        raise
