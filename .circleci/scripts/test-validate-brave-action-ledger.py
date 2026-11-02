#!/usr/bin/env python3
"""Regression tests for disjoint metric/checkpoint/pending ledger accounting."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile

VALIDATOR = Path(__file__).with_name("validate-brave-action-ledger.py")


def run(payload: dict, expected: int = 0) -> str:
    with tempfile.TemporaryDirectory(prefix="sandium-ledger-validation-") as temp:
        path = Path(temp) / "action-ledger.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(VALIDATOR), str(path)],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        if result.returncode != expected:
            raise AssertionError(
                "expected exit=%d got=%d\n%s"
                % (expected, result.returncode, result.stdout)
            )
        return result.stdout


def main() -> None:
    valid = {
        "schema_version": 2,
        "planned_total": 9,
        "completed": {"c1": {}, "c2": {}},
        "checkpoint_satisfied": {"s1": {}, "s2": {}, "s3": {}},
        "next_pending_action_keys": ["p1", "p2", "p3", "p4"],
    }
    output = run(valid)
    assert (
        "CHECKPOINT_ACTION_LEDGER=PASS metric_completed=2 "
        "checkpoint_satisfied=3 pending=4 total=9"
    ) in output, output

    # Backward compatibility: pre-checkpoint_satisfied schema-2 ledgers.
    legacy = {
        "schema_version": 2,
        "planned_total": 3,
        "completed": {"c1": {}},
        "next_pending_action_keys": ["p1", "p2"],
    }
    assert "checkpoint_satisfied=0 pending=2 total=3" in run(legacy)

    # A mismatch in the arithmetic must still be rejected.
    bad_total = dict(valid, planned_total=8)
    assert "category totals do not reconcile" in run(bad_total, expected=1)

    # Duplicates and overlapping categories are genuine identity errors.
    duplicate_pending = dict(valid, next_pending_action_keys=["p1", "p1", "p3", "p4"])
    assert "pending action identities are duplicated" in run(
        duplicate_pending, expected=1
    )
    overlapping = dict(valid, next_pending_action_keys=["p1", "p2", "p3", "c1"])
    assert "action identity categories overlap" in run(overlapping, expected=1)

    active = dict(valid, active_stage={"run_id": "unfinished"})
    assert "action stage is still active" in run(active, expected=1)

    print(
        "BRAVE_ACTION_LEDGER_VALIDATOR_TEST=PASS three-way accounting, "
        "legacy schema-2 compatibility, duplicate/overlap and total checks"
    )


if __name__ == "__main__":
    main()
