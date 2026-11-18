"""Bounded runtime selection using documented native checksum cache-key templates.

No cache API is assumed. A restored head descriptor determines selection files;
eight static restore steps can then choose the exact required payload keys.
"""
import argparse
import hashlib
import json
from pathlib import Path

from checkpoint import CheckpointError, Store, scan
from circleci_plan import MAX_LAYERS, restore_steps, verify_envelope
from cache_bundle import export_layer


def physical_key(logical_key):
    return "sandium-layer-v1-" + hashlib.sha256(logical_key.encode()).hexdigest()


def write_selections(plan, selection_root):
    restore_steps(plan)
    root = Path(selection_root)
    root.mkdir(parents=True, exist_ok=True)
    for index in range(MAX_LAYERS):
        logical = plan["layers"][index]["key"] if index < len(plan["layers"]) else f"unused-slot-{index}"
        (root / f"slot-{index}.key").write_bytes(logical.encode())
    (root / "plan.json").write_text(json.dumps(plan))


def static_restore_steps():
    result = []
    for index in range(MAX_LAYERS):
        result.extend([
            {"run": {"name": f"Clear layer {index} header", "command": f"rm -f .checkpoint-transport/slot-{index}.json"}},
            {"restore_cache": {"keys": [f'sandium-layer-v1-{{{{ checksum ".checkpoint-selection/slot-{index}.key" }}}}']}},
            {"run": {"name": f"Verify required layer {index}", "command":
                f"python3 native_slots.py verify --selection-root .checkpoint-selection --slot {index}"}},
        ])
    return result


def verify_selected(selection_root, slot, transport_root=".checkpoint-transport"):
    if not 0 <= slot < MAX_LAYERS:
        raise CheckpointError("Invalid slot")
    plan = json.loads((Path(selection_root) / "plan.json").read_text())
    restore_steps(plan)
    if slot >= len(plan["layers"]):
        return "UNUSED_SLOT"
    entry = plan["layers"][slot]
    if (Path(selection_root) / f"slot-{slot}.key").read_bytes() != entry["key"].encode():
        raise CheckpointError("Selection file differs from accepted plan")
    verify_envelope(Path(transport_root) / f"slot-{slot}.json", entry["key"], entry["sha256"])
    return "VERIFIED_REQUIRED_LAYER"


def maintenance_decision(plan, now, expected_remaining_seconds=7200, margin_seconds=86400):
    """Fail on expired dependencies; compact before expiry or exhausting slots.

    Producer must record actual configured cache retention, not assume 15 days.
    """
    restore_steps(plan)
    deadlines = [entry["expires_at"] for entry in plan["layers"]]
    if any(x <= now for x in deadlines):
        return "RESEED_REQUIRED_EXPIRED_CHAIN"
    if min(deadlines) <= now + expected_remaining_seconds + margin_seconds:
        return "COMPACT_BEFORE_BUILD"
    if len(plan["layers"]) >= MAX_LAYERS:
        return "COMPACT_BEFORE_BUILD"
    return "APPEND_INCREMENTAL_LAYER"


def compact_tree(source, new_store, compatibility, transport_root, cache_key, revision):
    """Real local compaction to a fresh immutable base; never changes old chain."""
    store = Store(new_store)
    if store.head("compacted") is not None:
        raise CheckpointError("Compaction store must be fresh")
    head = store.capture(source, "compacted", compatibility, None, revision)["head"]
    record = export_layer(store, head, compatibility, transport_root, 0, cache_key)
    entries = store.reconstruct(head, compatibility)
    if entries != scan(source):
        raise CheckpointError("Compaction tree differs")
    return {"head": head, "layers": [record]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    select = sub.add_parser("select")
    select.add_argument("--plan", required=True)
    select.add_argument("--selection-root", default=".checkpoint-selection")
    verify = sub.add_parser("verify")
    verify.add_argument("--selection-root", default=".checkpoint-selection")
    verify.add_argument("--slot", type=int, required=True)
    args = parser.parse_args()
    if args.command == "select":
        write_selections(json.loads(Path(args.plan).read_text()), args.selection_root)
    else:
        print(verify_selected(args.selection_root, args.slot))


if __name__ == "__main__":
    main()
