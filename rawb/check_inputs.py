#!/usr/bin/env python3
"""Read-only version/provenance check. Does not apply patches or admit a build."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import struct
import subprocess
import zipfile

BARE = "e4265e92c914765822bf31b6bb12afcb70bf7a77"
TAG = "fd861600035a4d34fb54c3f9e96f7a88af875f88"
BARE_TREE = "3cd8b22de30883a9e6211ac9e02dcc9f9bddbee5"
PATCH_TREE = "077ed0e167e74f331d45267044641f7939833f8c"
DONOR_CHROMIUM = "4b3d0dabb8250b6f152d2d85d79e7706e309d087"
TARGET = "52bdd21723d5db0c9ab11716d38feac74828cf84"
TARGET_VERSION_BLOB = "cfc8ae372a6c6194c81c495386721f38d26ded98"
CRX_NAME = "third_party/ublock_origin/uBlockOrigin-1.75.0.crx"
CRX_SHA = "d688ed3f0262ec4f8bdcd4c8f65987c5444c560aeb387a9e02aca1facdfa7046"
EXTENSION_ID = "fkgkibajhfbepljeaefdnfnegdcjomkh"
ASSET = "chrome/browser/resources/bare/ublock_origin.crx"


def require(test, what):
    if not test:
        raise ValueError(what)


def git(repo, *args):
    return subprocess.check_output(["git", "--no-replace-objects", "-C", str(repo), *args])


def rev(repo, name):
    return git(repo, "rev-parse", "--verify", name).decode().strip()


def verify_crx(data):
    require(len(data) == 4_568_084 and hashlib.sha256(data).hexdigest() == CRX_SHA,
            "Bundled extension differs from exact upstream CRX")
    require(data[:4] == b"Cr24", "Expected CRX wrapper")
    version, head = struct.unpack_from("<II", data, 4)
    require(version == 3 and 12 < 12 + head < len(data), "Invalid CRX3 header")
    archive = data[12 + head:]
    require(archive.startswith(b"PK\x03\x04"), "Expected extension ZIP payload")
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        require(z.namelist().count("manifest.json") == 1 and "LICENSE.txt" in z.namelist(),
                "Missing or ambiguous extension manifest or license")
        manifest = json.loads(z.read("manifest.json"))
    require(manifest["manifest_version"] == 2 and manifest["version"] == "1.75.0"
            and "launch-element-picker" in manifest["commands"],
            "Unexpected extension contract")
    return {"version": manifest["version"], "manifest_version": 2, "id": EXTENSION_ID,
            "sha256": CRX_SHA, "bytes": len(data), "source_asset_destination": ASSET}


def verify_version_contents(chromium):
    versions = git(chromium, "show", TARGET + ":chrome/VERSION").decode()
    found = dict(re.findall(r"^(MAJOR|MINOR|BUILD|PATCH)=(\d+)$", versions, re.M))
    require([found.get(x) for x in ("MAJOR", "MINOR", "BUILD", "PATCH")] ==
            ["158", "0", "8127", "42"], "Wrong target Chromium version")

def verify(bare, chromium, metadata_ref=None):
    require(rev(bare, "HEAD") == BARE and rev(bare, "HEAD^{tree}") == BARE_TREE
            and rev(bare, "v2.0.7^{tag}") == TAG and rev(bare, "v2.0.7^{commit}") == BARE
            and rev(bare, BARE + ":patches") == PATCH_TREE, "Wrong upstream Bare snapshot")
    require(rev(chromium, metadata_ref or "HEAD") == TARGET, "Wrong RawS Chromium revision")
    require(rev(chromium, TARGET + ":chrome/VERSION") == TARGET_VERSION_BLOB,
            "Wrong Chromium version blob")
    if metadata_ref is None:
        verify_version_contents(chromium)
    require(git(bare, "cat-file", "-t", TAG).strip() == b"tag", "Expected original annotated tag")
    require(not git(bare, "status", "--porcelain", "--untracked-files=all"),
            "Bare snapshot is not clean")
    files = git(bare, "ls-tree", "-r", "--name-only", "-z", BARE, "--", "patches").split(b"\0")
    files = [x.decode() for x in files if x]
    patches = [x for x in files if re.fullmatch(r"patches/[0-9]{7}\.patch", x)]
    require(len(patches) == 346 and patches == sorted(patches), "Canonical patch set incomplete")
    crx = verify_crx((bare / CRX_NAME).read_bytes())
    require(git(bare, "show", BARE + ":" + CRX_NAME) == (bare / CRX_NAME).read_bytes(),
            "Extension isn't tracked by the exact donor")
    return {"bare_commit": BARE, "bare_tree": BARE_TREE, "patch_tree": PATCH_TREE,
            "old_chromium": DONOR_CHROMIUM, "target_chromium": TARGET, "patch_count": len(patches),
            "bundled_ublock": crx, "chromium_worktree_gate": metadata_ref is None,
            "source_admitted": False, "apk_produced": False}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bare", required=True, type=Path)
    ap.add_argument("--chromium", required=True, type=Path)
    ap.add_argument("--metadata-ref", help="Exact commit ref in a sparse Git object store; no worktree verified")
    a = ap.parse_args()
    try:
        print(json.dumps(verify(a.bare.resolve(), a.chromium.resolve(), a.metadata_ref), indent=2))
    except (OSError, ValueError, KeyError, struct.error, zipfile.BadZipFile,
            subprocess.CalledProcessError) as exc:
        ap.exit(1, f"RawB input gate: {exc}\n")


if __name__ == "__main__":
    main()
