"""Generate a bounded CircleCI restore fragment; not a deployable build config.

Uses only restore_cache and run steps. Runtime-discovered descriptors still need
a setup/continuation integration, and status/promotion guards need trusted data.
"""
import argparse
import json
import re
import shlex
from checkpoint import CheckpointError

MAX_LAYERS = 8


def restore_steps(plan):
    layers = plan["layers"]
    if not 1 <= len(layers) <= MAX_LAYERS:
        raise CheckpointError("Layer bound exceeded; compact or reseed before this run")
    if len({x["key"] for x in layers}) != len(layers):
        raise CheckpointError("Duplicate layer key")
    steps = []
    for index, layer in enumerate(layers):
        key, sha = layer["key"], layer["sha256"]
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,220}", key) or not re.fullmatch(r"[0-9a-f]{64}", sha):
            raise CheckpointError("Unsafe key or digest")
        # Fixed slot paths prevent shell injection; each native cache stores its
        # own slot. Verify immediately so missing cache cannot reuse stale files.
        path = f".checkpoint-transport/slot-{index}.json"
        steps.extend([
            {"run": {"name": f"Clear checkpoint slot {index}", "command": f"rm -f {path}"}},
            {"restore_cache": {"keys": [key]}},
            {"run": {"name": f"Verify checkpoint layer {index}", "command":
                "python3 circleci_plan.py verify --path " + path + " --key " + shlex.quote(key) + " --sha256 " + sha}},
        ])
    return steps


def verify_envelope(path, expected_key, expected_hash):
    from pathlib import Path
    from checkpoint import digest
    try:
        raw = Path(path).read_bytes()
    except FileNotFoundError as exc:
        raise CheckpointError("Native cache did not restore required layer") from exc
    if digest(raw) != expected_hash:
        raise CheckpointError("Layer payload hash mismatch")
    payload = json.loads(raw)
    if payload["cache_key"] != expected_key:
        raise CheckpointError("Native prefix matched wrong cache")
    return payload


def promotion_decision(candidate, accepted):
    """Pure guard only; caller must supply verified facts under distributed lock.

    This is NOT distributed CAS. Re-read accepted within serialized publication.
    """
    if candidate["job_status"] != "success":
        return False, "Skipped/not_run/failed jobs are not publication evidence"
    if not candidate["receipt_valid"] or not candidate["chain_complete"]:
        return False, "No complete verified checkpoint receipt"
    if candidate["scope"] != accepted["scope"]:
        return False, "Incompatible publication scope"
    if candidate["pipeline_number"] < accepted["pipeline_number"]:
        return False, "Old pipeline rerun must not regress accepted state"
    if candidate["expected_head"] != accepted["head"]:
        return False, "Parent changed; re-evaluate rather than overwrite"
    if candidate["pipeline_number"] == accepted["pipeline_number"] and candidate["stage"] <= accepted["stage"]:
        return False, "Same or earlier stage cannot replace accepted successor"
    return True, "Eligible only while serialized publisher still owns this accepted state"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    generate = sub.add_parser("generate")
    generate.add_argument("plan")
    verify = sub.add_parser("verify")
    verify.add_argument("--path", required=True)
    verify.add_argument("--key", required=True)
    verify.add_argument("--sha256", required=True)
    args = parser.parse_args()
    if args.command == "generate":
        with open(args.plan) as f:
            print(json.dumps({"steps": restore_steps(json.load(f))}, indent=2))
    else:
        verify_envelope(args.path, args.key, args.sha256)


if __name__ == "__main__":
    main()
