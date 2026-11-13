#!/usr/bin/env python3
"""Experimental single-mode real-state bridge. Native cache operations live in YAML."""
from progress import advance, Watchdog
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import importlib.util

from checkpoint import Store, CheckpointError, atomic_json, encoded, digest, verify_blob, scan
from cache_bundle import export_layer, validate_bundles
from native_slots import physical_key
from consume_restore import restore_consuming

ROOT = Path(os.environ.get("CIRCLE_WORKING_DIRECTORY", ".")).resolve()
STATE = ROOT / ".checkpoint-state"
TRANSPORT = ROOT / ".checkpoint-transport"
INCOMING = ROOT / ".checkpoint-incoming"
HEAD = ROOT / ".checkpoint-head" / "receipt.json"
# Product compatibility excludes implementation edits so valid incremental work can
# survive a patch. Exact recipe identity independently guards completion shortcuts.
_recipe_spec = importlib.util.spec_from_file_location("product_recipe", Path(__file__).resolve().parents[1] / "scripts/product_recipe.py")
_recipe_module = importlib.util.module_from_spec(_recipe_spec)
_recipe_spec.loader.exec_module(_recipe_module)
PRODUCT_IDENTITY = _recipe_module.identity()
COMPAT = PRODUCT_IDENTITY["compatibility"]
RECIPE = PRODUCT_IDENTITY["recipe"]


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_json(path, value)


def scope():
    return os.environ["SANDIUM_EXPERIMENT_SCOPE"]


def gate():
    if os.environ.get("SANDIUM_EXPERIMENT_REVIEWED") != "true":
        raise CheckpointError("Experimental writer/serialization review not confirmed; refusing to run")
    if os.environ.get("CIRCLE_PROJECT_REPONAME") != "Sandium-2":
        raise CheckpointError("Only existing Sandium-2 project is permitted for seed cache access")
    if not scope().startswith("sandium-exp-single-v1-"):
        raise CheckpointError("Nonexperimental namespace forbidden")
    STATE.mkdir(exist_ok=True)
    (STATE / "scope-key").write_text(scope() + "-" + COMPAT)
    if not (STATE / "job-start.json").exists():
        save(STATE / "job-start.json", {"epoch": time.time()})


def valid(receipt):
    payload = receipt["payload"]
    if receipt["id"] != digest(encoded(payload)) or payload["scope"] != scope() or payload["compatibility"] != COMPAT:
        raise CheckpointError("Head integrity/scope mismatch")
    if min(x["expires_at"] for x in payload["plan"]["layers"]) <= time.time():
        raise CheckpointError("Expired chain; explicit reseed to a new experimental namespace required")
    if payload["pipeline"] > int(os.environ["SANDIUM_PIPELINE_NUMBER"]):
        raise CheckpointError("Older pipeline rerun refused")
    return payload


def halt():
    subprocess.run(["circleci-agent", "step", "halt"], check=True)


def disk_guard(phase, required):
    usage = shutil.disk_usage(ROOT)
    print("FLOW_DISK", json.dumps({"phase": phase, "total": usage.total,
        "used": usage.used, "free": usage.free, "required": required}), flush=True)
    if usage.free < required:
        raise CheckpointError("Insufficient disk for " + phase)


def select(seed=False):
    gate()
    if not HEAD.exists():
        if not seed:
            raise CheckpointError("No accepted experimental checkpoint; no base-only fallback")
        if os.environ.get("SANDIUM_ALLOW_SEED_IMPORT") != "true":
            raise CheckpointError("Initial seed import not explicitly enabled")
        return
    receipt = read(HEAD)
    payload = valid(receipt)
    if seed:
        print("EXPERIMENT_SEED=ALREADY_PRESENT")
        halt()
        return
    stage = int(os.environ["SANDIUM_STAGE"])
    if payload["apk_verified"] and payload["source"] == os.environ["CIRCLE_SHA1"]:
        print("APK_ALREADY_VERIFIED_WITH_SAVED_CHECKPOINT", payload["workflow"])
        halt()
        return
    if stage > 1 and (payload["workflow"], payload["stage"], payload["source"]) != (
            os.environ["CIRCLE_WORKFLOW_ID"], stage - 1, os.environ["CIRCLE_SHA1"]):
        raise CheckpointError("Exact prior stage receipt missing; refusing old-base fallback")
    save(STATE / "selected.json", receipt)
    layers = payload["plan"]["layers"]
    if not 1 <= len(layers) <= 8:
        raise CheckpointError("Invalid chain length")
    disk_guard("before-native-layer-restore", sum(x["content_bytes"] for x in layers) + 32 * 1024**2)
    for i in range(8):
        (STATE / f"slot-{i}.key").write_text(layers[i]["key"] if i < len(layers) else f"unused-{scope()}-{i}")


def ingest(index):
    layers = read(STATE / "selected.json")["payload"]["plan"]["layers"]
    if index >= len(layers):
        print("UNUSED_SLOT", index)
        return
    header = INCOMING / "slot.json"
    if not header.exists():
        raise CheckpointError("Required cache missing")
    raw = header.read_bytes()
    if digest(raw) != layers[index]["sha256"] or read(header)["cache_key"] != layers[index]["key"]:
        raise CheckpointError("Wrong/prefix-collided or corrupt cache")
    TRANSPORT.mkdir(exist_ok=True)
    shutil.move(str(header), TRANSPORT / f"slot-{index}.json")
    shutil.move(str(INCOMING / "payload"), TRANSPORT / f"slot-{index}")


def restore():
    plan = read(STATE / "selected.json")["payload"]["plan"]
    disk_guard("before-tree-reconstruction", 32 * 1024**2)
    bundles = validate_bundles(plan, TRANSPORT, COMPAT)
    store = Store(ROOT / ".checkpoint-store")
    for directory, envelope, raw in bundles:
        for blob, size in envelope["blobs"].items():
            target = store.path / "blobs" / blob
            if not target.exists():
                os.link(directory / "blobs" / blob, target)
            verify_blob(target, {"blob": blob, "size": size})
        (store.path / "manifests" / envelope["head"]).write_bytes(raw)
    restore_consuming(store, plan["head"], COMPAT, ROOT / "brave-work")
    save(store.path / "refs" / "main", {"head": plan["head"]})
    save(STATE / "restored-proof.json", {"receipt": read(STATE / "selected.json")["id"], "head": plan["head"]})
    # All source state is now verified; free duplicate downloaded payloads.
    shutil.rmtree(TRANSPORT)
    # Only manifests are needed for the next delta comparison. Do not retain a
    # second full copy of all imported content throughout compilation.
    shutil.rmtree(store.path / "blobs")
    (store.path / "blobs").mkdir()


def verify_restored():
    selected = read(STATE / "selected.json")
    valid(selected)
    proof = read(STATE / "restored-proof.json")
    if proof != {"receipt": selected["id"], "head": selected["payload"]["plan"]["head"]}:
        raise CheckpointError("Restored state proof does not match selected complete chain")


def quiescent():
    spec = importlib.util.spec_from_file_location("shards_quiescence", Path(__file__).resolve().parents[1] / "scripts/sandium-checkpoint-shards.py")
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    if module.find_open_writers(ROOT / "brave-work"):
        raise CheckpointError("Open writable descriptors in build tree; snapshot refused")


def capture_linked(store, parent):
    """Hardlink only during the post-build quiescent save window; never resume writers."""
    work = ROOT / "brave-work"
    quiescent()
    old = store.reconstruct(parent, COMPAT)
    current = scan(work)
    changed = {k: v for k, v in current.items() if old.get(k) != v}
    old_blobs = {v["blob"] for v in old.values() if v["kind"] == "file"}
    advance(phase="capture-link-and-verify")
    for name, entry in changed.items():
        if entry["kind"] == "file" and entry["blob"] not in old_blobs:
            target = store.path / "blobs" / entry["blob"]
            if not target.exists():
                os.link(work / name, target)
            # Hardlink shares the scanned inode; the mandatory second complete scan
            # validates bytes and metadata after linking while writers remain stopped.
            if not os.path.samefile(work / name, target):
                verify_blob(target, entry)  # duplicate-content path, not the same inode
        advance(items=1)
    quiescent()
    if scan(work) != current:
        raise CheckpointError("Tree changed during snapshot")
    layer = {"schema": 1, "parent": parent, "compatibility": COMPAT, "revision": os.environ["CIRCLE_SHA1"],
             "changed": changed, "deleted": sorted(old.keys() - current.keys()), "state_hash": digest(encoded(current))}
    head = digest(encoded(layer))
    save(store.path / "manifests" / head, layer)
    save(store.path / "refs" / "main", {"head": head})
    return {"head": head}


def capture(seed=False):
    gate()
    selected = None if seed else read(STATE / "selected.json")
    previous = selected["payload"]["plan"] if selected else None
    parent = previous["head"] if previous else None
    layers = previous["layers"] if previous else []
    # Quiescence is a hard gate, not an assumption from successful shell exit.
    processes = subprocess.check_output(["ps", "-eo", "comm="], text=True).splitlines()
    if any(x.strip() in ("siso", "ninja", "clang", "clang++", "ld.lld") for x in processes):
        raise CheckpointError("Build writers still running; snapshot refused")
    # Snapshot/export share immutable hardlinks during this save-only window.
    # Native archive scratch overhead remains unmeasured; retain a minimum reserve.
    advance(phase="measure-source-size")
    source_bytes = 0
    for p in (ROOT / "brave-work").rglob("*"):
        if p.is_file() and not p.is_symlink():
            source_bytes += p.stat().st_size
        advance(items=1)
    reserve = max(32 * 1024**2, min(8 * 1024**3, source_bytes // 8))
    disk_guard("before-native-cache-packaging-minimum-reserve", reserve)
    compact = bool(layers) and (len(layers) >= 8 or min(x["expires_at"] for x in layers) < time.time() + 172800)
    if compact:
        store = Store(ROOT / ".checkpoint-compacted-store")
        parent, layers = None, []
    else:
        store = Store(ROOT / ".checkpoint-store")
    result = capture_linked(store, parent)
    slot = len(layers)
    key = scope() + "-" + os.environ["CIRCLE_WORKFLOW_ID"] + "-" + os.environ["CIRCLE_BUILD_NUM"] + "-" + result["head"]
    record = export_layer(store, result["head"], COMPAT, ROOT / ".checkpoint-export", slot, key, link_blobs=True)
    record["expires_at"] = int(time.time()) + 15 * 86400
    INCOMING.mkdir(exist_ok=True)
    shutil.move(str(ROOT / ".checkpoint-export" / f"slot-{slot}.json"), INCOMING / "slot.json")
    shutil.move(str(ROOT / ".checkpoint-export" / f"slot-{slot}"), INCOMING / "payload")
    (STATE / "outgoing.key").write_text(key)
    plan = {"head": result["head"], "layers": layers + [record]}
    status = ROOT / "brave-apk" / "status.txt"
    apk = status.exists() and all(x in status.read_text().splitlines() for x in (
        "BUILD_FINISHED=true", "APK_ARCHIVE_VALID=true", "APK_SIGNATURE_VALID=true", "APK_PACKAGE_ID_VALID=true", "APK_BRANDING_VALID=true"))
    payload = {"scope": scope(), "compatibility": COMPAT, "source": os.environ["CIRCLE_SHA1"],
        "pipeline": int(os.environ["SANDIUM_PIPELINE_NUMBER"]), "workflow": os.environ["CIRCLE_WORKFLOW_ID"],
        "stage": 0 if seed else int(os.environ["SANDIUM_STAGE"]), "plan": plan,
        "apk_verified": apk and not seed, "previous_receipt": selected["id"] if selected else None}
    save(STATE / "candidate.json", {"id": digest(encoded(payload)), "payload": payload})
    print("CHECKPOINT_CAPTURE", json.dumps({"slot": slot, "compact": compact, "new_content_bytes": record["content_bytes"]}))


def publish():
    gate()
    candidate = read(STATE / "candidate.json")
    valid(candidate)
    if HEAD.exists():
        old = read(HEAD)
        prior = valid(old)
        current = candidate["payload"]
        if current["previous_receipt"] != old["id"] or (current["pipeline"], current["stage"]) <= (prior["pipeline"], prior["stage"]):
            raise CheckpointError("Stale/nonadvancing publication refused")
    save(HEAD, candidate)


def final_gate():
    payload = valid(read(HEAD))
    status = ROOT / "brave-work" / ".sandium" / "build-stage-status.txt"
    if status.exists() and "BUILD_REASON=ACTION_FAILED_HANDOFF" in status.read_text():
        raise CheckpointError("Deterministic build failure checkpoint preserved; do not repeat unchanged action")
    if int(os.environ["SANDIUM_STAGE"]) == 5 and not payload["apk_verified"]:
        raise CheckpointError("Five stages exhausted without verified APK")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["gate", "select", "seed-select", "ingest", "restore", "verify-restored", "capture", "seed-capture", "publish", "final"])
    parser.add_argument("--slot", type=int)
    args = parser.parse_args()
    started = read(STATE / "job-start.json")["epoch"] if (STATE / "job-start.json").exists() else time.time()
    # Conservative 55-minute job allowance, reserving 10 minutes for native save/head steps.
    reserve = 600 if args.phase in ("capture", "seed-capture", "restore") else 0
    remaining = 3300 - (time.time() - started) - reserve
    budget = min(1800, remaining)
    if budget <= 0:
        raise CheckpointError("No checkpoint budget remains before native-save reserve")
    print("FLOW_BUDGET", json.dumps({"phase": args.phase, "seconds": round(budget), "native_save_reserve": reserve}), flush=True)
    advance(phase=args.phase)
    with Watchdog(budget):
        {"gate": gate, "select": select, "seed-select": lambda: select(True), "ingest": lambda: ingest(args.slot),
     "restore": restore, "verify-restored": verify_restored, "capture": capture, "seed-capture": lambda: capture(True), "publish": publish,
     "final": final_gate}[args.phase]()
