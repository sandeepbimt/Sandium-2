#!/usr/bin/env python3
"""Read-only exact-base/checksum/applicability gate; never applies or builds."""
import argparse
import hashlib
from pathlib import Path
import subprocess

PIN = "44a84b1f89d9a35287289d6a3d493e362f5a5123"
SHA = "38d5e39840304f66e29ddef7fd09bea11bc0a31bc2eae47bb576c51d33b26fc4"

def preflight(core: Path, patch: Path):
    if hashlib.sha256(patch.read_bytes()).hexdigest() != SHA:
        raise ValueError("Unreviewed extension patch digest")
    def git(*args):
        return subprocess.check_output(["git", "-C", str(core), *args], text=True).strip()
    if git("rev-parse", "HEAD") != PIN:
        raise ValueError("EXT0 requires the exact pinned Brave source")
    if git("status", "--porcelain", "--untracked-files=no"):
        raise ValueError("EXT0 base must be clean; product composition is a separate gate")
    subprocess.run(["git", "-C", str(core), "apply", "--check", str(patch.resolve())], check=True)
    print("PASS: exact base and patch applicability only. GN/native/runtime NOT validated.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", required=True, type=Path)
    args = parser.parse_args()
    preflight(args.core, Path(__file__).with_name("brave-android-extensions.patch"))
