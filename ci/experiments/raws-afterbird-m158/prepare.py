#!/usr/bin/env python3
"""Apply the exact first-step patch only to a disposable RawS M158 checkout."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

KIT = Path(__file__).resolve().parent
OUTPUT = Path("out/RawSAfterbirdM158/args.gn")

def sha(blob):
    return hashlib.sha256(blob).hexdigest()

def command(source, *argv):
    return subprocess.run(
        ["git", "-C", str(source), *argv], check=True,
        stdout=subprocess.PIPE, text=True,
    ).stdout.strip()

def safe_path(root, relative):
    relative = Path(relative)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Expected a relative checkout path")
    p = root / relative
    for child in (p, *p.parents):
        if child == root:
            return p
        if child.is_symlink():
            raise ValueError(f"Refusing symlink in checkout path: {relative}")
    raise ValueError("Checkout path not contained")

def check_inputs(path, args):
    pin = json.loads((KIT / "inputs.json").read_text())
    if command(path, "rev-parse", "--show-toplevel") != str(path):
        raise ValueError("Supply the Chromium checkout root")
    if command(path, "rev-parse", "HEAD") != pin["chromium_commit"]:
        raise ValueError("Wrong Chromium commit: use pinned RawS Chromium 158")
    if sha(args) != pin["args_sha256"]:
        raise ValueError("Expected unmodified RawS ci/args.gn")
    if sha((KIT / "desktop-android.patch").read_bytes()) != pin["desktop_patch_sha256"]:
        raise ValueError("The experiment patch differs from the review")
    fragment = (KIT / "args.gn.fragment").read_bytes()
    if sha(fragment) != pin["args_fragment_sha256"]:
        raise ValueError("The experiment args fragment differs from the review")
    for name, wanted in pin["unchanged"].items():
        if sha(safe_path(path, name).read_bytes()) != wanted:
            raise ValueError(f"Stock policy/buildflag file differs: {name}")
    for name, hashes in pin["paths"].items():
        if sha(safe_path(path, name).read_bytes()) != hashes["before"]:
            raise ValueError(f"Apply the exact #1537 RawS overlay first: {name}")
    actual = command(path, "apply", "--numstat", str(KIT / "desktop-android.patch"))
    if {line.split("\t")[-1] for line in actual.splitlines()} != set(pin["paths"]):
        raise ValueError("Experiment patch changes unexpected paths")
    command(path, "apply", "--check", str(KIT / "desktop-android.patch"))
    return pin, args.rstrip(b"\n") + b"\n\n" + fragment

def prepare(path, args, apply=False):
    path = path.resolve(strict=True)
    pin, rendered = check_inputs(path, args)
    dest = safe_path(path, OUTPUT)
    if dest.exists():
        raise ValueError("Experiment output already exists; use a fresh checkout/output")
    if apply:
        command(path, "apply", str(KIT / "desktop-android.patch"))
        try:
            for name, hashes in pin["paths"].items():
                if sha(safe_path(path, name).read_bytes()) != hashes["after"]:
                    raise ValueError(f"Unexpected experiment result: {name}")
            dest.parent.mkdir(parents=True, exist_ok=True)
            with dest.open("xb") as f:
                f.write(rendered)
        except Exception:
            command(path, "apply", "--reverse", str(KIT / "desktop-android.patch"))
            raise
    return rendered

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--raws-args", required=True, type=Path)
    parser.add_argument("--apply", action="store_true",
                        help="Modifies the disposable checkout and writes experiment-only args")
    ns = parser.parse_args()
    prepare(ns.source, ns.raws_args.read_bytes(), ns.apply)
    print("Applied" if ns.apply else "Preflight passed (no file changes)")
