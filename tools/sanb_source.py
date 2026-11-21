#!/usr/bin/env python3
"""Fail-closed SanB source preparation. No build, signing or credential access."""
from __future__ import annotations
import argparse, hashlib, json, os, re, subprocess
from pathlib import Path

BARE = "e4265e92c914765822bf31b6bb12afcb70bf7a77"
CHROMIUM = "52bdd21723d5db0c9ab11716d38feac74828cf84"
VERSION = "158.0.8127.42"
REPO = Path(__file__).resolve().parent.parent
PLAN = REPO / "sanb-source/receipt.json"
DEPOT = "fed8b43f48c4f4c2ac0c34aafbf0ec07a4e600cb"
SRC_URL = "https://chromium.googlesource.com/chromium/src.git"
DEPOT_URL = "https://chromium.googlesource.com/chromium/tools/depot_tools.git"
FORBIDDEN_PATHS = re.compile(r"(?i)(?:bare_bundled_extensions|bare_filter_subscriber|bare_ubo_update|BareUboUpdate|ublock_origin|[\w.-]+\.crx(?:$|/))")
FORBIDDEN_ADDITIONS = re.compile(
    r"\b(?:uBlockOrigin[./_-]|(?:kStore)?UBlockOriginId|bare_bundled_extension_assets|"
    r"bare_bundled_extensions_loader|BareBundledExtensionsLoader|BareUboUpdate(?:Jni)?|"
    r"bare_ubo_(?:auto_update|check_now)|bare_filter_subscriber|BareFilterEnabled|"
    r"Chrome\.BareFilter|InstallBundledExtensions|bareSeededLists|fkgkibajhfbepljeaefdnfnegdcjomkh|"
    r"cjpalhdlnbpafiamejdnhcphjbkeiagm)\b", re.IGNORECASE)

def fail(text: str):
    raise SystemExit(text)

def sha(data: bytes):
    return hashlib.sha256(data).hexdigest()

def checked_path(base: Path, relative: object):
    if not isinstance(relative, str):
        fail("Missing relative asset identity")
    p = Path(relative)
    if p.is_absolute() or '..' in p.parts or '.git' in p.parts:
        fail("Patch path outside the independently reviewed root")
    real = (base / p).resolve()
    if not real.is_relative_to(base) or not real.is_file():
        fail(f"Required reviewed asset missing: {p}")
    return real

def parse_patch(raw: bytes):
    content = raw.decode("utf-8", "strict")
    touched = set()
    for line in content.splitlines():
        if line.startswith("diff --git "):
            import shlex
            p = shlex.split(line)
            if len(p) != 4:
                fail("Noncanonical patch path")
            for prefix, value in zip(("a/", "b/"), p[2:]):
                if not value.startswith(prefix):
                    fail("Noncanonical patch path")
                path = Path(value[2:])
                if path.is_absolute() or '..' in path.parts or '.git' in path.parts or FORBIDDEN_PATHS.search(value[2:]):
                    fail(f"Unexpected or bundle-linked path: {path}")
                touched.add(str(path))
        elif line.startswith("+") and not line.startswith("+++") and FORBIDDEN_ADDITIONS.search(line[1:]):
            fail(f"Banned bundled-extension plumbing in release additions: {line[:160]}")
    if not touched:
        fail("Empty patch cannot establish a SanB overlay")
    return touched

def verify(receipt: Path):
    if not receipt.is_file():
        fail("Reviewed SanB source receipt is not present")
    payload = json.loads(receipt.read_text())
    exact = {"schema":1,"bare":BARE,"chromium":CHROMIUM,"version":VERSION,
             "android_desktop":True,"embedded_ublock":False}
    for key, expected in exact.items():
        if type(payload.get(key)) is not type(expected) or payload.get(key) != expected:
            fail(f"Wrong SanB {key} in source receipt")
    if payload.get("status") != "rebase-complete-reviewed" or payload.get("unresolved_conflicts") != []:
        fail("SanB source not admitted: rebase or exclusions are incomplete")
    if payload.get("depot_tools") != DEPOT:
        fail("Wrong depot_tools pin")
    rel = receipt.resolve().parent
    patch = checked_path(rel, payload.get("patch"))
    raw = patch.read_bytes()
    if sha(raw) != payload.get("patch_sha256"):
        fail("SanB patch digest mismatch")
    scopes = parse_patch(raw)
    if set(payload.get("paths", [])) != scopes:
        fail("Patch touched-path inventory does not match reviewed scope")
    attribution = checked_path(rel, payload.get("bare_license"))
    if sha(attribution.read_bytes()) != payload.get("bare_license_sha256"):
        fail("Bare attribution digest mismatch")
    return payload, patch

def run(*args, cwd=None, env=None):
    subprocess.run([str(a) for a in args], cwd=cwd, env=env, check=True)

def gitout(cwd, *args):
    return subprocess.check_output(["git", "-C", str(cwd), *args], text=True).strip()

def checkout(dest: Path, url: str, ref: str):
    dest.mkdir()
    run("git", "init", "-q", cwd=dest)
    run("git", "remote", "add", "origin", url, cwd=dest)
    run("git", "fetch", "--no-tags", "--depth", "1", "origin", ref, cwd=dest)
    run("git", "checkout", "-q", "--detach", "FETCH_HEAD", cwd=dest)
    if gitout(dest, "rev-parse", "HEAD") != ref:
        fail("Wrong upstream pin after checkout")

def prepare(receipt: Path, workspace: Path, result: Path):
    payload, patch = verify(receipt)
    if workspace.exists() or workspace.is_symlink():
        fail("SanB workspace must be a dedicated nonexistent path")
    workspace.mkdir(parents=False)
    workspace = workspace.resolve()
    src, depot = workspace/"src", workspace/"depot_tools"
    checkout(depot, DEPOT_URL, DEPOT)
    checkout(src, SRC_URL, CHROMIUM)
    versions = dict(x.split("=",1) for x in (src/"chrome/VERSION").read_text().strip().splitlines())
    seen = ".".join(versions[k].strip() for k in ("MAJOR", "MINOR", "BUILD", "PATCH"))
    if seen != VERSION:
        fail("Chromium source pin's version doesn't match")
    run("git", "apply", "--check", "--index", "--whitespace=error-all", patch, cwd=src)
    run("git", "apply", "--index", "--whitespace=error-all", patch, cwd=src)
    # Review source overlay exactly and tell gclient that Chromium src is unmanaged;
    # gclient is to realize its pinned DEPS, not rewrite the source recipe.
    reviewed_tree = gitout(src, "write-tree")
    (workspace/".gclient").write_text(
        "solutions = " + repr([{"name":"src","url":SRC_URL,"managed":False,
          "custom_deps":{},"custom_vars":{"checkout_pgo_profiles":True}}])
        + "\ntarget_os = ['android']\n")
    env = dict(os.environ)
    env["DEPOT_TOOLS_UPDATE"]="0"
    env["PATH"]=str(depot)+os.pathsep+env.get("PATH","")
    run(depot/"gclient", "sync", "--nohooks", "--no-history", cwd=workspace, env=env)
    if gitout(src,"rev-parse","HEAD") != CHROMIUM:
        fail("Dependency sync unexpectedly changed Chromium HEAD")
    run("git","diff","--exit-code",cwd=src)
    if gitout(src, "write-tree") != reviewed_tree:
        fail("Dependency sync changed staged SanB source content")
    # Emit exact source receipt bytes only after verifying dependency checkout
    # did not replace any reviewed overlay paths.
    applied=set(gitout(src,"diff","--cached","--name-only").splitlines())
    if applied != set(payload["paths"]):
        fail("Prepared checkout does not match the reviewed file inventory")
    for path in sorted(applied):
        f = src / path
        if f.is_symlink():
            fail(f"Review required for a source-overlay symlink: {path}")
        if f.is_file():
            with f.open("rb") as artifact:
                if artifact.read(4) == b"Cr24":
                    fail(f"Embedded CRX payload in reviewed source: {path}")
    emit(result, payload)

def emit(result, payload):
    if result.resolve() == PLAN.resolve() or result.resolve().is_relative_to(PLAN.parent.resolve()):
        fail("Source receipt output must not replace reviewed SanB assets")
    with result.open("x") as sink:
        sink.write(json.dumps(payload,sort_keys=True,indent=2)+"\n")

def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest="command", required=True)
    v=sub.add_parser("verify")
    v.add_argument("--receipt", type=Path, required=True)
    m=sub.add_parser("prepare")
    m.add_argument("--receipt", type=Path, required=True)
    m.add_argument("--workspace", type=Path, required=True)
    args=p.parse_args()
    if args.command=="verify":
        payload,_=verify(PLAN)
        emit(args.receipt,payload)
    else:
        prepare(PLAN,args.workspace,args.receipt)

if __name__=="__main__":
    main()
