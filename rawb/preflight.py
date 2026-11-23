#!/usr/bin/env python3
"""Exact Source + Android GN-only preflight. No credentials, build, APK, or cache."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from check_inputs import ASSET, BARE, CRX_NAME, CRX_SHA, TARGET, require, verify

ROOT=Path(__file__).resolve().parent.parent
SOURCE=ROOT/"rawb"
DEPS="fed8b43f48c4f4c2ac0c34aafbf0ec07a4e600cb"
BARE_REMOTE="https://github.com/BareBrowser/bare-browser"
CHROMIUM_REMOTE="https://chromium.googlesource.com/chromium/src.git"
DEPOT_REMOTE="https://chromium.googlesource.com/chromium/tools/depot_tools.git"
ASSET_TARGET="//chrome/browser/resources/bare:bare_bundled_extension_assets"
BROWSER_TARGET="//chrome/browser/extensions:extensions"
APK_TARGET="//chrome/android:chrome_public_apk"

def sha(p):
    with p.open("rb") as f:
        return hashlib.file_digest(f,"sha256").hexdigest()

def admission():
    # A source-only receipt or omitted security review must not start a checkout.
    p=SOURCE/"source-admission.json"
    require(p.is_file() and not p.is_symlink(),"No reviewed, complete RawB source admission")
    m=json.loads(p.read_bytes())
    want={"bare":BARE,"chromium":TARGET,"depot_tools":DEPS,"patch_count":346,
          "bundled_ublock_sha256":CRX_SHA,"contains_brave_adblock":False,
          "contains_raws_overlay":False,"contains_1442_port":False,
          "remaining_holds":0,"source_admitted_for_graph":True,
          "upstream_bare_extension_policy":True,"graph_only":True}
    require(all(m.get(k)==v and type(m.get(k)) is type(v) for k,v in want.items()),
            "Complete RawB source graph admission has not been proven")
    compressed=SOURCE/"rawb-m158.patch.zst"
    require(compressed.is_file() and sha(compressed)==m["patch_zstd_sha256"],
            "RawB pinned M158 patch bundle digest mismatch")
    require(sha(SOURCE/"bare-arm64.gn")==m["gn_args_sha256"],"GN args changed")
    require((SOURCE/"bare-arm64.gn").read_text().count("is_desktop_android = true")==1,
            "Lost Android Desktop extension build")
    return m

def run(cmd,cwd,env,capture=False):
    print("RawB phase command:",cmd[0],cmd[1],flush=True)
    return subprocess.run(cmd,cwd=cwd,env=env,check=True,text=True,
                          stdout=subprocess.PIPE if capture else None).stdout

def main():
    pa=argparse.ArgumentParser(description=__doc__)
    pa.add_argument("--check-only",action="store_true")
    a=pa.parse_args()
    m=admission()
    if a.check_only:
        print("Exact patch receipt verified; no compile or APK.")
        return
    disk=shutil.disk_usage(ROOT).free
    require(disk >= 130*2**30,"Worker too small for isolated Chromium dependency preparation")
    require(not (ROOT/".rawb-preflight").exists(),"Refusing existing work directory")
    work=ROOT/".rawb-preflight"; work.mkdir(mode=0o700)
    home=work/"home"; home.mkdir(mode=0o700)
    env={k:v for k,v in os.environ.items() if k in {"PATH","LANG","LC_ALL"}}
    env.update(HOME=str(home),GIT_CONFIG_NOSYSTEM="1",GIT_TERMINAL_PROMPT="0",
               DEPOT_TOOLS_UPDATE="0",PYTHONDONTWRITEBYTECODE="1")
    run(["git","clone","--depth=1","--branch","v2.0.7","--single-branch",BARE_REMOTE,"bare"],work,env)
    for path,remote,pin in [("depot_tools",DEPOT_REMOTE,DEPS),("src",CHROMIUM_REMOTE,TARGET)]:
        (work/path).mkdir()
        run(["git","init","-q"],work/path,env)
        run(["git","remote","add","origin",remote],work/path,env)
        run(["git","fetch","--depth=1","origin",pin],work/path,env)
        run(["git","checkout","--detach",pin],work/path,env)
    env["PATH"]=str(work/"depot_tools")+os.pathsep+env["PATH"]
    src=work/"src"; bare=work/"bare"
    donor=verify(bare,src)
    run(["gclient","config","--unmanaged","--name","src",CHROMIUM_REMOTE],work,env)
    with (work/".gclient").open("a") as f:
        f.write("\ntarget_os = ['android']\n")
    run(["gclient","sync","--nohooks","--shallow","--no-history",
         "--revision","src@"+TARGET],work,env)
    # Validate pinned base again after sync. Overlay paths are checked before materialization.
    verify(bare,src)
    patch_path=work/"rawb-m158.patch"
    with patch_path.open("xb") as sink:
        subprocess.run(["zstd","-q","-d","-c",str(SOURCE/"rawb-m158.patch.zst")],
                       env=env,stdout=sink,check=True)
    require(sha(patch_path)==m["patch_sha256"], "Unpacked rebased Chromium patch digest mismatch")
    patch=str(patch_path)
    run(["git","apply","--check","--index",patch],src,env)
    run(["git","apply","--index",patch],src,env)
    staged=run(["git","diff","--cached","--name-only","-z"],src,env,True).split("\0")
    require(not any(re.search(r"(^|/)(brave|raws-adblock|sandium_adblock)(/|$)",p,re.I)
                    for p in staged if p), "Unexpected competing blocker path")
    ext=src/ASSET
    require(ext.resolve().is_relative_to(src) and not ext.exists(),"Invalid CRX asset destination")
    ext.parent.mkdir(exist_ok=True,parents=True)
    shutil.copyfile(bare/CRX_NAME,ext)
    require(sha(ext)==CRX_SHA,"CRX staging digest mismatch")
    run(["gclient","runhooks"],work,env)
    out="out/RawB-arm64"
    (src/out).mkdir(parents=True)
    shutil.copyfile(SOURCE/"bare-arm64.gn",src/out/"args.gn")
    run(["gn","gen",out,"--fail-on-unused-args"],src,env)
    deps=run(["gn","desc",out,APK_TARGET,"deps","--all"],src,env,True).splitlines()
    loader=run(["gn","desc",out,BROWSER_TARGET,"sources"],src,env,True).splitlines()
    asset_gn=(src/"chrome/browser/resources/bare/BUILD.gn").read_text()
    require(any(x.strip().startswith(ASSET_TARGET) for x in deps),"uBlock APK asset not linked")
    require(any(x.strip().endswith("/bare_bundled_extensions_loader.cc") for x in loader)
            and any(x.strip().startswith(BROWSER_TARGET) for x in deps),"Native Bare loader not linked")
    require('renaming_sources = [ "ublock_origin.crx" ]' in asset_gn
            and "disable_compression = true" in asset_gn,"Wrong Bare asset source or compression")
    require(not any(re.search(r"(^|/)(brave|raws-adblock|sandium_adblock)([/:]|$)",p,re.I)
                    for p in deps),"Unexpected competing blocker in APK dependencies")
    # This is a cold planned edge list, not a build duration or cache measurement.
    planned=run(["ninja","-n","-C",out,"chrome_public_apk"],src,env,True)
    path=ROOT/".rawb-preflight-evidence"; path.mkdir(exist_ok=False)
    results={"graph_verified":True,"apk_produced":False,"compile_started":False,
             "checkout":os.environ.get("CIRCLE_SHA1"),"source_patch_sha256":m["patch_sha256"],
             "chromium":TARGET,"bare":BARE,"ublock":donor["bundled_ublock"],
             "ninja_planned_output_lines":len(planned.splitlines()),"free_bytes_after_graph":shutil.disk_usage(work).free}
    (path/"graph.json").write_text(json.dumps(results,indent=2)+"\n")
    print("Verified Bare Chromium M158 graph; no compilation or APK.",flush=True)
if __name__=="__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as e:
        raise SystemExit(f"RawB preflight stopped: {e}") from None
