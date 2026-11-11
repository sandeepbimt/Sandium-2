#!/usr/bin/env python3
"""Read-only validator/selector for separate Sandium source/build checkpoints."""
import argparse, hashlib, json, re, sys
from datetime import datetime, timezone
from pathlib import Path

BASE="3c8004b0b01a3e7b65daee40d84c971048fe43ae"
HEX=re.compile(r"^[0-9a-f]{64}$")
COMMON=("checkpoint_id","checkpoint_kind","status","created_at","base_reference","branch","source","build_identity")
SOURCE=("brave_tag","brave_sha","chromium_tag","chromium_sha","gclient_sha256")
BUILD=("target","build_type","gn_args_sha256","toolchain_fingerprint")

class Invalid(ValueError): pass

def stamp(value):
    try: result=datetime.fromisoformat(value.replace("Z","+00:00"))
    except (TypeError,ValueError) as exc: raise Invalid("invalid created_at") from exc
    if result.tzinfo is None: raise Invalid("created_at must include timezone")
    return result.astimezone(timezone.utc)

def sha256(path):
    h=hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()

def load(path):
    try: data=json.loads(path.read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError) as exc: raise Invalid(f"manifest unreadable: {exc}") from exc
    if not isinstance(data,dict) or data.get("schema_version")!=1: raise Invalid("unsupported schema_version")
    missing=[key for key in COMMON if key not in data]
    if missing: raise Invalid("missing fields: "+",".join(missing))
    kind=data["checkpoint_kind"]
    if kind not in ("pinned_source","compiled_build"): raise Invalid("invalid checkpoint_kind")
    if data["status"]!="READY": raise Invalid("checkpoint is not READY")
    if not isinstance(data["checkpoint_id"],str) or not data["checkpoint_id"].strip(): raise Invalid("empty checkpoint_id")
    if not isinstance(data["branch"],str) or not data["branch"].strip(): raise Invalid("empty branch")
    if not isinstance(data["source"],dict) or not isinstance(data["build_identity"],dict): raise Invalid("identity fields must be objects")
    required=SOURCE+(BUILD if kind=="compiled_build" else ())
    missing=[key for key in required if key not in data["source"] and key not in data["build_identity"]]
    if missing: raise Invalid("missing identity fields: "+",".join(missing))
    stamp(data["created_at"])
    if data["base_reference"]!=BASE: raise Invalid("wrong canonical base reference")
    files=data.get("files",[])
    if not isinstance(files,list): raise Invalid("files must be a list")
    for item in files:
        if not isinstance(item,dict) or not isinstance(item.get("path"),str): raise Invalid("invalid file record")
        rel=Path(item["path"])
        if rel.is_absolute() or ".." in rel.parts: raise Invalid("unsafe relative path")
        target=path.parent/rel
        if not target.is_file(): raise Invalid(f"missing payload: {rel}")
        if not isinstance(item.get("size_bytes"),int) or target.stat().st_size!=item["size_bytes"]: raise Invalid(f"size mismatch: {rel}")
        if not isinstance(item.get("sha256"),str) or not HEX.fullmatch(item["sha256"]) or sha256(target)!=item["sha256"]: raise Invalid(f"checksum mismatch: {rel}")
    return data

def select(candidates,kind,expected):
    accepted=[]; rejected=[]
    for candidate in candidates:
        path=candidate/"manifest.json" if candidate.is_dir() else candidate
        try:
            manifest=load(path)
            if manifest["checkpoint_kind"]!=kind: raise Invalid("checkpoint class mismatch")
            actual={"checkpoint_kind":manifest["checkpoint_kind"],"branch":manifest["branch"],"base_reference":manifest["base_reference"],**manifest["source"],**manifest["build_identity"]}
            mismatches=[key for key,value in expected.items() if actual.get(key)!=value]
            if mismatches: raise Invalid("incompatible fields: "+",".join(mismatches))
            accepted.append((stamp(manifest["created_at"]),manifest["checkpoint_id"],path,manifest))
        except Invalid as exc: rejected.append(f"{path}: {exc}")
    if not accepted: raise Invalid("no compatible READY checkpoint\n"+"\n".join(rejected))
    _,_,path,manifest=max(accepted,key=lambda item:(item[0],item[1]))
    return path,manifest

def main():
    parser=argparse.ArgumentParser(description=__doc__); sub=parser.add_subparsers(dest="command",required=True)
    validate=sub.add_parser("validate"); validate.add_argument("manifest",type=Path)
    choose=sub.add_parser("select"); choose.add_argument("--kind",choices=("pinned_source","compiled_build"),required=True); choose.add_argument("--expected",type=Path,required=True); choose.add_argument("candidates",nargs="+",type=Path)
    args=parser.parse_args()
    try:
        if args.command=="validate":
            manifest=load(args.manifest); print(f"SANDIUM_CHECKPOINT_VALID=PASS kind={manifest['checkpoint_kind']} id={manifest['checkpoint_id']}")
        else:
            expected=json.loads(args.expected.read_text(encoding="utf-8"))
            if not isinstance(expected,dict): raise Invalid("expected identity must be a JSON object")
            path,manifest=select(args.candidates,args.kind,expected)
            print(json.dumps({"selected_manifest":str(path),"checkpoint_id":manifest["checkpoint_id"],"checkpoint_kind":manifest["checkpoint_kind"],"created_at":manifest["created_at"]},sort_keys=True))
        return 0
    except (OSError,json.JSONDecodeError,Invalid) as exc:
        print(f"SANDIUM_CHECKPOINT_SELECTION=REJECTED {exc}",file=sys.stderr); return 2

if __name__=="__main__": raise SystemExit(main())
