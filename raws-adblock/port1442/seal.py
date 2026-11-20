#!/usr/bin/env python3
"""Integrate a reviewed port delta into the immutable RawS restore-only format."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess

BASE = "c86ff1a8575e49c0dff22610315004c0c1a48a95"
REF = "d3e82450867d3be2c5724244c4077b0457814d55"
CORE = "bd6d26d1bced03c17a98baa86d2cd3425d543d1b"
VENDOR = "brave/third_party/rust/chromium_crates_io/vendor/adblock-v0_13/src/"
RECIPE = "raws-adblock/production-restore-recipe.json"
POST = "raws-adblock/production-postimages"
SHA = re.compile(r"[a-f0-9]{64}")

def digest(data):
    return hashlib.sha256(data).hexdigest()

def safe_file(root, rel):
    path = PurePosixPath(rel)
    if path.is_absolute() or path.as_posix() != rel or ".." in path.parts or ".git" in path.parts:
        raise ValueError(f"Invalid path: {rel}")
    candidate = root / rel
    if not candidate.is_file() or candidate.resolve() != candidate:
        raise ValueError(f"Missing or symlinked file: {rel}")
    return candidate

def seal(repo, delta, output):
    if output.exists() or output.is_symlink():
        raise ValueError("Output must be a new directory")
    recipe = json.loads(subprocess.check_output(["git", "-C", str(repo), "show", f"{BASE}:{RECIPE}"]))
    files = recipe["files"]
    receipt = json.loads(safe_file(delta, "delta-receipt.json").read_bytes())
    if (receipt["raws"], receipt["reference"], receipt["brave"], receipt["chromium"]) != (
            BASE, REF, CORE, recipe["chromium_revision"]):
        raise ValueError("Delta does not match reviewed sources")
    records = receipt["files"]
    if not records:
        raise ValueError("Empty delta")
    staged = {}
    postimages = {}
    tracked = []
    generated = []
    for name, record in sorted(records.items()):
        data = safe_file(delta, name).read_bytes()
        before, after = record["before"], record["after"]
        if digest(data) != after or before == after:
            raise ValueError(f"Changed or redundant delta payload: {name}")
        if before is not None and (not isinstance(before,str) or not SHA.fullmatch(before)):
            raise ValueError(f"Invalid preimage: {name}")
        old = files.get(name)
        if old:
            if old["after_sha256"] != before:
                raise ValueError(f"Not based on active #1462 overlay: {name}")
            old["after_sha256"] = after
        else:
            if before is None:
                if not name.startswith(("components/sandium_adblock/", "chrome/browser/raws/")):
                    raise ValueError(f"Unexpected untracked path: {name}")
                if not name.startswith("components/sandium_adblock/"):
                    generated.append(name)
            else:
                if not name.startswith(("chrome/", "content/", "third_party/blink/")):
                    raise ValueError(f"Unexpected tracked path: {name}")
                tracked.append(name)
            files[name] = {"before_sha256": before, "after_sha256": after}
        if name.startswith("brave/"):
            if not name.startswith(VENDOR) or not old or old.get("mode", "644") != "644":
                raise ValueError(f"Unexpected vendor delta scope: {name}")
            staged[name] = {"before": before, "after": after}
        postimages[after] = data
    if not staged or not tracked or not generated:
        raise ValueError("Expected vendor, tracked, and generated Android inputs")
    output.mkdir()
    (output / "postimages").mkdir()
    manifest = (json.dumps(recipe, sort_keys=True, indent=2) + "\n").encode()
    (output / "production-restore-recipe.json").write_bytes(manifest)
    for sha, data in postimages.items():
        (output / "postimages" / sha).write_bytes(data)
    proof = {"manifest_sha256": digest(manifest), "delta_sha256": digest(
        (delta / "delta-receipt.json").read_bytes()), "staged_vendor_delta": staged,
        "extra_tracked": tracked, "extra_generated": generated}
    (output / "admission.json").write_text(json.dumps(proof, sort_keys=True, indent=2) + "\n")
    print(json.dumps({k:(len(v) if isinstance(v,(list,dict)) else v) for k,v in proof.items()}))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("repo", "delta", "output"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    seal(args.repo.resolve(), args.delta.resolve(), args.output.absolute())
