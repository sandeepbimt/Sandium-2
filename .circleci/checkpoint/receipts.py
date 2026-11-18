"""Validated checkpoint receipt/head envelopes, without pretending hashes authenticate.

Native cache publication must occur inside a verified single-writer boundary.
These functions validate data and ordering; they are not distributed CAS.
"""
import argparse
import json
import re
from pathlib import Path

from checkpoint import CheckpointError, atomic_json, digest, encoded, valid_id
from circleci_plan import restore_steps


def envelope(payload):
    return {"receipt_id": digest(encoded(payload)), "payload": payload}


def verify(receipt, scope, now):
    payload = receipt["payload"]
    if digest(encoded(payload)) != receipt["receipt_id"]:
        raise CheckpointError("Receipt integrity failure")
    if payload["schema"] != 1 or payload["scope"] != scope:
        raise CheckpointError("Receipt scope mismatch")
    if not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", payload["source_revision"]):
        raise CheckpointError("Invalid source commit")
    valid_id(payload["head"])
    restore_steps(payload["plan"])
    if payload["plan"]["head"] != payload["head"]:
        raise CheckpointError("Receipt plan/head mismatch")
    if payload["expires_at"] <= now:
        raise CheckpointError("Receipt chain expired")
    if payload["expires_at"] != min(layer["expires_at"] for layer in payload["plan"]["layers"]):
        raise CheckpointError("Expiry does not cover all dependencies")
    if payload["snapshot_status"] not in ("checkpoint_saved", "apk_and_checkpoint_saved"):
        raise CheckpointError("No saved checkpoint evidence")
    if not isinstance(payload["pipeline_number"], int) or payload["pipeline_number"] < 1:
        raise CheckpointError("Invalid pipeline number")
    if not isinstance(payload["stage"], int) or not 1 <= payload["stage"] <= 5:
        raise CheckpointError("Invalid stage")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", payload["workflow_id"]):
        raise CheckpointError("Invalid workflow identity")
    return payload


def select_for_stage(receipt, scope, now, pipeline_number, workflow_id, stage, source_revision):
    payload = verify(receipt, scope, now)
    if payload["pipeline_number"] > pipeline_number:
        raise CheckpointError("Old rerun cannot consume/promote newer accepted state")
    if stage > 1:
        if (payload["pipeline_number"], payload["workflow_id"], payload["stage"], payload["source_revision"]) != (
                pipeline_number, workflow_id, stage - 1, source_revision):
            raise CheckpointError("Missing exact predecessor stage; no base-only fallback")
    return payload["plan"]


def prepare_receipt(plan, scope, source_revision, pipeline_number, workflow_id, stage,
                    now, previous=None, apk_verified=False, native_saves_completed=False, compacted=False):
    if not native_saves_completed:
        raise CheckpointError("Cannot publish before native save steps complete")
    restore_steps(plan)
    if previous:
        old_plan = select_for_stage(previous, scope, now, pipeline_number, workflow_id, stage, source_revision)
        predecessor = previous["receipt_id"]
        parent_head = previous["payload"]["head"]
        if compacted:
            if len(plan["layers"]) != 1 or plan["layers"][0]["parent"] is not None:
                raise CheckpointError("Compaction must publish an independent base")
        elif (len(plan["layers"]) != len(old_plan["layers"]) + 1 or
              plan["layers"][:-1] != old_plan["layers"] or plan["layers"][-1]["parent"] != parent_head):
            raise CheckpointError("Delta receipt does not extend exact accepted chain")
    else:
        if stage != 1 or len(plan["layers"]) != 1:
            raise CheckpointError("Only explicit initial base may lack predecessor")
        predecessor, parent_head = None, None
        if plan["layers"][0]["parent"] is not None:
            raise CheckpointError("Initial seed must be independent")
    payload = {"schema": 1, "scope": scope, "source_revision": source_revision,
               "pipeline_number": pipeline_number, "workflow_id": workflow_id, "stage": stage,
               "head": plan["head"], "plan": plan, "previous_receipt": predecessor,
               "previous_head": parent_head, "created_at": now,
               "expires_at": min(layer["expires_at"] for layer in plan["layers"]),
               "snapshot_status": "apk_and_checkpoint_saved" if apk_verified else "checkpoint_saved"}
    result = envelope(payload)
    verify(result, scope, now)
    return result


def publication_guard(candidate, accepted, now, serialization_verified=False):
    if not serialization_verified:
        raise CheckpointError("Distributed single-writer boundary not verified")
    scope = candidate["payload"]["scope"]
    new = verify(candidate, scope, now)
    if accepted:
        old = verify(accepted, scope, now)
        if new["previous_receipt"] != accepted["receipt_id"]:
            raise CheckpointError("Accepted receipt advanced; stale publication refused")
        if (new["pipeline_number"], new["stage"]) <= (old["pipeline_number"], old["stage"]):
            raise CheckpointError("Non-advancing or older rerun publication refused")
    elif new["previous_receipt"] is not None:
        raise CheckpointError("Missing accepted predecessor")
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--accepted")
    parser.add_argument("--now", type=int, required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--serialization-verified", action="store_true")
    args = parser.parse_args()
    candidate = json.loads(Path(args.candidate).read_text())
    accepted = json.loads(Path(args.accepted).read_text()) if args.accepted else None
    publication_guard(candidate, accepted, args.now, args.serialization_verified)
    atomic_json(Path(args.output), candidate)


if __name__ == "__main__":
    main()
