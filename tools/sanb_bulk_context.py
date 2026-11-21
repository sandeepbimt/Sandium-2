#!/usr/bin/env python3
"""No-fetch chronological replay of every auditable Bare patch on exact Chromium pins.

Sparse evidence is not compatibility. Patches with unread old objects or any
unresolved predecessor on the same path are held, never labelled conflicts.
Never emits a build-admission receipt or executes downloaded source.
"""
from __future__ import annotations
import argparse
import collections
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tarfile
import tempfile

import sanb_replay_groups as helpers

ROOT=helpers.ROOT
REPO=ROOT/"chromium158"
OLD="4b3d0dabb8250b6f152d2d85d79e7706e309d087"
TARGET=helpers.PIN
DONOR="e4265e92c914765822bf31b6bb12afcb70bf7a77"
DONOR_TREE="3cd8b22de30883a9e6211ac9e02dcc9f9bddbee5"
DONOR_TAG="fd861600035a4d34fb54c3f9e96f7a88af875f88"
NO_NETWORK=dict(os.environ,GIT_ALLOW_PROTOCOL="",GIT_NO_LAZY_FETCH="1")

def repository(repo,*args, **options):
    return helpers.git(repo,*args,**options)

def names(raw):
    result=set()
    for record in raw.splitlines():
        if not record.startswith(b"diff --git "):
            continue
        parts=shlex.split(record.decode("utf-8"))
        if len(parts)!=4 or not all(p.startswith(pref) for p,pref in zip(parts[2:],("a/","b/"))):
            raise ValueError(f"Unsupported donor patch header: {record[:140]!r}")
        for text in parts[2:]:
            p=Path(text[2:])
            if p.is_absolute() or ".." in p.parts or ".git" in p.parts:
                raise ValueError(f"Unsafe donor patch header: {record[:140]!r}")
            result.add(str(p))
    return result

def trees(pin,paths,repo=REPO):
    raw=repository(repo,"ls-tree","-r","-z",pin,"--",*sorted(paths)).stdout
    out={}
    for entry in raw.split(b"\0"):
        if entry:
            left, path=entry.split(b"\t",1)
            mode,obj,oid=left.decode().split()
            out[path.decode()]={"mode":mode,"type":obj,"oid":oid}
    return out

def in_git(objects,repo=REPO):
    if not objects:
        return set()
    # Promisor miss queries are fatal on some Git versions. Enumerate only
    # physically local objects, then intersect with the exact requested set.
    lines=subprocess.run(["git","-C",str(repo),"cat-file","--batch-all-objects",
                          "--unordered","--batch-check=%(objectname) %(objecttype) %(objectsize)"],
                         capture_output=True,check=True,env=NO_NETWORK).stdout
    return objects & {m.group(1).decode()
                      for m in re.finditer(rb"^([a-f0-9]{40}) blob [0-9]+$",lines,re.M)}

def discover(blob_names, fixture_roots):
    by_name=collections.defaultdict(set)
    for tree in blob_names:
        for path,row in tree.items():
            if row["type"]=="blob":
                by_name[Path(path).name].add(row["oid"])
    files={}
    roots=[]
    for item in fixture_roots:
        if item.is_dir() and not item.is_symlink() and item.resolve() not in roots:
            roots.append(item.resolve())
    for item in roots:
        for parent,dirs, fs in os.walk(item,followlinks=False):
            dirs[:]=[x for x in dirs if x not in {".git",".venv",".local-audit","__pycache__","node_modules"}
                     and (x != "third_party" or item.name=="pin")]
            for n in fs:
                if n not in by_name:
                    continue
                p=Path(parent)/n
                if p.is_symlink() or p.stat().st_size>32*1024*1024:
                    continue
                raw=p.read_bytes()
                oid=hashlib.sha1(f"blob {len(raw)}\0".encode()+raw,usedforsecurity=False).hexdigest()
                if oid in by_name[n]:
                    files.setdefault(oid,p)
    return files

def blob_bytes(repo, path, oid):
    data=path.read_bytes() if path else repository(repo,"cat-file","blob",oid).stdout
    if hashlib.sha1(f"blob {len(data)}\0".encode()+data,usedforsecurity=False).hexdigest()!=oid:
        raise ValueError("Unexpected preimage bytes while staging expected blob: "+oid)
    return data

def check_build_candidates(all_paths, available, rows, groups, old, repo):
    fatal_if_exports={"exclude-bundled-extension","hold-independent-mv2","mixed-needs-hunk-review","hold-security-baseline"}
    blocked={}
    actions=[]
    catalog=collections.Counter()
    with tempfile.TemporaryDirectory(prefix="sanb-canonical-replay-") as temp:
        work=Path(temp)
        helpers.git(work,"init","-q")
        for name,value in all_paths.items():
            oid=value["oid"]
            mode=value["mode"]
            if oid not in available or mode not in ("100644","100755"):
                continue
            body=blob_bytes(repo,available[oid],oid)
            p=work/name
            p.parent.mkdir(parents=True,exist_ok=True)
            p.write_bytes(body)
            p.chmod(int(mode,8)&0o777)
        helpers.git(work,"add","-A")
        inventory=helpers.git(work,"write-tree").stdout.decode().strip()
        for row,patch,scope in rows:
            number=row["id"]
            label=row["classification"]
            missing=sorted(p for p in scope if p in all_paths and
                           (all_paths[p]["oid"] not in available or
                            all_paths[p]["mode"] not in ("100644","100755")))
            deps={p:blocked[p] for p in sorted(scope) if p in blocked}
            item={"id":number,"group":groups.get(number,"other-canonical"),"classification":label,
                  "paths":len(scope)}
            actions.append(item)
            if not old and label in fatal_if_exports:
                status="policy-hold"
            elif missing:
                status="not-run-unread-first-preimage"
                item["unread"]={p:all_paths[p]["oid"] for p in missing}
            elif deps:
                status="not-run-predecessor-hold"
                item["predecessor_hold"]=deps
            else:
                check=helpers.git(work,"apply","--check","--index","--whitespace=nowarn",patch,check=False)
                if check.returncode:
                    failure=check.stderr.decode(errors="replace")
                    if not any(x in failure for x in ("patch does not apply","does not exist in index",
                            "does not match index","already exists","wrong file type","invalid path",
                            "patch failed","does not exist")):
                        raise ValueError(f"Git replay infrastructure failed for {number}: {failure}")
                    status="actual-context-conflict"
                    item["stderr"]=failure
                else:
                    helpers.git(work,"apply","--index","--whitespace=nowarn",patch)
                    status="applied-context-only"
            item["status"]=status
            catalog[status]+=1
            if status!="applied-context-only":
                for p in scope:
                    blocked.setdefault(p,number)
        # Never distribute this source-oriented partial replay: even a contextual
        # pass may be on the wrong privacy/policy or build side of separation.
        replay_tree=helpers.git(work,"write-tree").stdout.decode().strip()
    unread={p:x["oid"] for p,x in all_paths.items() if x["oid"] not in available}
    return {"available_first_preimage_paths":len(all_paths)-len(unread),
            "available_first_preimage_unique_blobs":len({x["oid"] for x in all_paths.values()
                                                         if x["oid"] in available}),
            "unread_first_preimage_paths":len(unread),"unread_first_preimage_unique_blobs":len(set(unread.values())),
            "tracked_paths":len(all_paths),"unread":unread,
            "status_counts":dict(sorted(catalog.items())),"group_status_counts":{
                g:dict(sorted(collections.Counter(a["status"] for a in actions if a["group"]==g).items()))
                for g in sorted({a["group"] for a in actions})},
            "known_fixture_tree":inventory,"review_replay_tree":replay_tree,"actions":actions}

def pack_preimages(out, repo, known):
    archive=out/"sanb-pinned-preimages.tar.gz"
    packed=[]
    excluded=[]
    with archive.open("xb") as stream, gzip.GzipFile(filename="",mode="wb",fileobj=stream,mtime=0) as gz:
        with tarfile.open(fileobj=gz,mode="w|") as tar:
            for oid,where in sorted(known.items()):
                raw=blob_bytes(repo,where,oid)
                if raw.startswith(b"Cr24"):
                    excluded.append(oid)
                    continue
                entry=tarfile.TarInfo("blobs/"+oid)
                entry.size=len(raw)
                entry.mode=0o644
                entry.mtime=0
                tar.addfile(entry,io.BytesIO(raw))
                packed.append(oid)
    with archive.open("rb") as f:
        digest=hashlib.file_digest(f,"sha256").hexdigest()
    return {"name":archive.name,"bytes":archive.stat().st_size,"sha256":digest,
            "crx_magic_excluded":excluded,"packed_blob_count":len(packed),"packed_blobs":packed}


def pinned_inventory(chromium_repo, bare_repo, inventory):
    chromium_repo, bare_repo = chromium_repo.resolve(strict=True), bare_repo.resolve(strict=True)
    inventory = inventory.resolve(strict=True)
    for pin in (OLD,TARGET):
        actual=repository(chromium_repo,"rev-parse",pin+"^{commit}").stdout.decode().strip()
        if actual!=pin: raise ValueError("Wrong pinned Chromium input: "+actual)
    proven=helpers.git(bare_repo,"rev-parse","HEAD","HEAD^{tree}","refs/tags/v2.0.7").stdout.decode().splitlines()
    if proven!=[DONOR,DONOR_TREE,DONOR_TAG]:
        raise ValueError("Wrong annotated Bare v2.0.7 source provenance")
    exact=json.loads(inventory.read_text())
    if exact.get("schema")!=1 or exact.get("bare")!=DONOR or len(exact.get("chronology",[]))!=346:
        raise ValueError("Wrong canonical Bare source inventory")
    rows=[]
    last=""
    for row in exact["chronology"]:
        number=row["id"]
        if not re.fullmatch(r"[0-9]{7}",number) or number<=last:
            raise ValueError("Out-of-order/malformed canonical patch identity")
        last=number
        patch=bare_repo/f"patches/{number}.patch"
        b=patch.read_bytes()
        if hashlib.sha256(b).hexdigest()!=row["sha256"]:
            raise ValueError(f"Wrong donor patch contents: {patch}")
        rows.append((row,patch,names(b)))
    scopes=set().union(*(scope for _,_,scope in rows))
    trees_by_pin={pin:trees(pin,scopes,chromium_repo) for pin in (OLD,TARGET)}
    unique={row["oid"] for tree in trees_by_pin.values() for row in tree.values() if row["type"]=="blob"}
    return rows, scopes, trees_by_pin, unique


def run(out, fixture_roots, chromium_repo=REPO, bare_repo=ROOT/"bare",
        inventory=ROOT/"sanb-source/canonical-inventory.json", write_pack=False):
    chromium_repo=chromium_repo.resolve(strict=True)
    rows,scopes,trees_by_pin,unique=pinned_inventory(chromium_repo,bare_repo,inventory)
    discovered=discover(trees_by_pin.values(),fixture_roots)
    present=in_git(unique-set(discovered),chromium_repo)
    known=discovered|dict.fromkeys(present)
    groups={f"{n:07}":g for g,ns in helpers.GROUPS.items() for n in ns}
    groups|={f"{n:07}":"native-nav-appearance" for n in (32,106,147)}
    result={"schema":1,"status":"contextual-evidence-only","bare":DONOR,"target":TARGET,"donor_base":OLD,
            "canonical_patch_count":len(rows),"unique_paths_with_old_and_new_headers":len(scopes),
            "unique_upstream_blobs_both_pins":len(unique),"readable_unique_upstream_blobs_both_pins":len(known),
            "unread_unique_upstream_blobs_both_pins":len(unique-set(known)),
            "count_method":"Per pin, first preimage means upstream blob before donor chronology. M158 applies only known materialized and no held predecessor; M157 is provenance pass with no SanB exclusions."}
    for pin,mode in ((TARGET,"target_m158"),(OLD,"donor_m157")):
        result[mode]=check_build_candidates(trees_by_pin[pin],known,rows,groups,pin==OLD,chromium_repo)
    if write_pack:
        result["preimages_pack"]=pack_preimages(out,chromium_repo,known)
    (out/"bulk-context.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path)
    parser.add_argument("--emit-missing-wants",type=Path)
    parser.add_argument("--fixtures",action="append",type=Path,default=[])
    parser.add_argument("--chromium-repo",type=Path,default=REPO)
    parser.add_argument("--bare-repo",type=Path,default=ROOT/"bare")
    parser.add_argument("--inventory",type=Path,default=ROOT/"sanb-source/canonical-inventory.json")
    parser.add_argument("--require-all-preimages",action="store_true")
    parser.add_argument("--pack-preimages",action="store_true")
    ns=parser.parse_args()
    if bool(ns.output)==bool(ns.emit_missing_wants):
        parser.error("Specify exactly one of --output or --emit-missing-wants")
    if ns.emit_missing_wants:
        if ns.fixtures or ns.pack_preimages or ns.require_all_preimages:
            parser.error("Missing-wants mode inventories only upstream Git object availability")
        _,_,_,unique=pinned_inventory(ns.chromium_repo,ns.bare_repo,ns.inventory)
        missing=sorted(unique-in_git(unique,ns.chromium_repo))
        with ns.emit_missing_wants.open("x") as f:
            for oid in missing: f.write(oid+"\n")
        print(f"{len(missing)}/{len(unique)} pinned Chromium blobs are not in the checked Git object store")
        return
    ns.output.mkdir()
    fixture_roots=ns.fixtures
    if ns.chromium_repo.resolve()==REPO.resolve():
        fixture_roots=[ROOT/"pin-fixtures/new",ROOT/"pin-fixtures/old",*fixture_roots]
    result=run(ns.output,fixture_roots,ns.chromium_repo,ns.bare_repo,ns.inventory,ns.pack_preimages)
    print(json.dumps({k:(v["status_counts"]|{c:v[c] for c in (
        "tracked_paths","available_first_preimage_paths","available_first_preimage_unique_blobs",
        "unread_first_preimage_paths","unread_first_preimage_unique_blobs")})
        if k in ("target_m158","donor_m157") else v for k,v in result.items() if k!="preimages_pack"},indent=2,sort_keys=True))
    if ns.require_all_preimages and result["unread_unique_upstream_blobs_both_pins"]:
        raise SystemExit(3)

if __name__=="__main__":
    main()
