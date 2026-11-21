#!/usr/bin/env python3
"""Measure scoped Bare→Chromium hunk application on exact upstream blobs.

Each independently reviewed group gets a clean index. Missing preimages never
become hunk conflicts; a predecessor failure within a chain stops that chain.
This tool writes evidence and scoped review diffs, never an admission receipt.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PIN = "52bdd21723d5db0c9ab11716d38feac74828cf84"
GIT_ENV = dict(os.environ, GIT_NO_LAZY_FETCH="1")
GROUPS = {
    "ntp-chrome-tips": [17],
    "ntp-card-visibility-defaults": [25],
    "recently-closed-local-only": [184],
    "fullscreen-video-layout": [12,13],
    "app-menu-bottom-sheet": [253,254],
    "app-menu-and-modal-canonical-chain": [205,253,254],
    "ntp-toolbar-gesture-direction": [260],
    "toolbar-gemini-setting": [20],
    "toolbar-glass-presentation": [206],
    "ntp-search-vertical-spacing-chain": [26,31],
    "ntp-search-icon-capture": [45],
    "ntp-disable-downloaded-popular-sites": [111],
    "settings-search-fade": [185],
    "incognito-close-create-handoff": [189],
}

def git(cwd, *args, check=True):
    return subprocess.run(["git","-C",str(cwd),*map(str,args)], env=GIT_ENV,
                          capture_output=True, check=check)

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def tree(repo, paths):
    result = {}
    for entry in git(repo,"ls-tree","-z",PIN,"--",*sorted(paths)).stdout.split(b'\0'):
        if entry:
            fields, rawpath = entry.split(b'\t',1)
            mode,t,oid = fields.decode().split()
            if t != "blob" or mode not in ("100644","100755"):
                raise ValueError("Unreviewed non-file fixture: "+str(rawpath))
            result[rawpath.decode()] = (mode,oid)
    return result

def run(out):
    source = ROOT/"chromium158"
    fixtures = ROOT/"pin-fixtures/new"
    index = json.loads((ROOT/"sanb-source/canonical-inventory.json").read_text())
    rows = {int(x["id"]):x for x in index["chronology"]}
    results = {}
    for group, ids in GROUPS.items():
        paths={p for n in ids for p in rows[n]["paths"]}
        expected = tree(source, paths)
        with tempfile.TemporaryDirectory(prefix="sanb-contextual-") as tmp:
            dst = Path(tmp)
            git(dst, "init", "-q")
            absent = {}
            ignored_new = sorted(paths - set(expected))
            for name, (mode,oid) in expected.items():
                f=fixtures/name
                result=git(source,"cat-file","blob",oid,check=False) if not f.is_file() else None
                if not f.is_file() and result.returncode != 0:
                    absent[name]=oid
                    continue
                data=f.read_bytes() if f.is_file() else result.stdout
                of=dst/name
                of.parent.mkdir(parents=True,exist_ok=True)
                of.write_bytes(data)
                of.chmod(int(mode,8) & 0o777)
                found=git(dst,"hash-object","--",name).stdout.decode().strip()
                if found != oid:
                    raise ValueError(f"Mismatched pinned preimage: {name}, {found} != {oid}")
            item={"ids":ids,"paths":sorted(paths),"preimage_blobs":{p:o for p,(_,o) in expected.items()},
                  "untracked_upstream_paths":ignored_new,"missing_preimage_files":absent,"attempts":[]}
            results[group]=item
            if absent:
                item["status"]="not-run-missing-preimages"
                continue
            git(dst,"add","-A")
            baseline=git(dst,"write-tree").stdout.decode().strip()
            for n in ids:
                p=ROOT/f"bare/patches/{n:07}.patch"
                if sha(p.read_bytes()) != rows[n]["sha256"]:
                    raise ValueError(f"Wrong Bare canonical patch bytes: {n}")
                check=git(dst,"apply","--check","--index","--whitespace=nowarn",p,check=False)
                if check.returncode:
                    item["attempts"].append({"id":n,"result":"context-conflict","stderr":check.stderr.decode()})
                    item["status"]="context-conflict"
                    item["dependent_not_tested"]=ids[ids.index(n)+1:]
                    break
                git(dst,"apply","--index","--whitespace=nowarn",p)
                item["attempts"].append({"id":n,"result":"applied"})
            else:
                diff=git(dst,"diff","--binary","--full-index",baseline).stdout
                (out/f"{group}.patch").write_bytes(diff)
                item["status"]="context-applied-not-build-verified"
                item["patch_sha256"]=sha(diff)
    measures={"schema":1,"chromium":PIN,"bare":index["bare"],"groups":results,
              "applied_count":sum(a["result"]=="applied" for i in results.values() for a in i["attempts"]),
              "observed_context_conflict_count":sum(a["result"]=="context-conflict" for i in results.values() for a in i["attempts"])}
    (out/"contextual-replay.json").write_text(json.dumps(measures,indent=2,sort_keys=True)+"\n")
    return measures

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    a.output.mkdir() # No reuse of stale patches after a blocked group.
    result=run(a.output)
    print(json.dumps(result,indent=2,sort_keys=True))
