#!/usr/bin/env python3
"""Validate Sandium's checkpoint action ledger without conflating its counters.

Accounting categories are intentionally disjoint:
  metric-completed: observed successful Siso action records
  checkpoint-satisfied: absent from the live Siso frontier after restore
  pending: identities the live Siso dry-run still schedules

Older schema-2 ledgers without checkpoint_satisfied remain readable.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def fail(message: str) -> "NoReturn":
    print("CHECKPOINT_ACTION_LEDGER=FAIL " + message, file=sys.stderr)
    raise SystemExit(1)


def validate(path: Path) -> tuple[int, int, int, int]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail("cannot read ledger: %s" % exc)

    if not isinstance(data, dict) or data.get("schema_version") != 2:
        fail("unsupported or invalid ledger schema")
    if data.get("active_stage"):
        fail("action stage is still active")

    completed = data.get("completed", {})
    satisfied = data.get("checkpoint_satisfied", {})
    pending = data.get("next_pending_action_keys")
    total = data.get("planned_total")

    if not isinstance(completed, dict):
        fail("completed must be an object")
    if not isinstance(satisfied, dict):
        fail("checkpoint_satisfied must be an object")
    if not isinstance(pending, list):
        fail("next_pending_action_keys must be a list")
    if isinstance(total, bool) or not isinstance(total, int) or total < 0:
        fail("planned_total must be a non-negative integer")
    if any(not isinstance(key, str) or not key for key in completed):
        fail("completed contains an invalid action identity")
    if any(not isinstance(key, str) or not key for key in satisfied):
        fail("checkpoint_satisfied contains an invalid action identity")
    if any(not isinstance(key, str) or not key for key in pending):
        fail("pending contains an invalid action identity")

    pending_set = set(pending)
    if len(pending_set) != len(pending):
        fail("pending action identities are duplicated")

    completed_set = set(completed)
    satisfied_set = set(satisfied)
    overlap_completed_satisfied = completed_set & satisfied_set
    overlap_completed_pending = completed_set & pending_set
    overlap_satisfied_pending = satisfied_set & pending_set
    if overlap_completed_satisfied or overlap_completed_pending or overlap_satisfied_pending:
        fail(
            "action identity categories overlap "
            "(completed/satisfied=%d completed/pending=%d satisfied/pending=%d)"
            % (len(overlap_completed_satisfied), len(overlap_completed_pending),
               len(overlap_satisfied_pending))
        )

    metric_completed_count = len(completed_set)
    checkpoint_satisfied_count = len(satisfied_set)
    pending_count = len(pending_set)
    reconciled_total = (
        metric_completed_count + checkpoint_satisfied_count + pending_count
    )
    if total != reconciled_total:
        fail(
            "category totals do not reconcile "
            "(metric_completed=%d checkpoint_satisfied=%d pending=%d "
            "planned_total=%d reconciled_total=%d)"
            % (metric_completed_count, checkpoint_satisfied_count,
               pending_count, total, reconciled_total)
        )
    return total, metric_completed_count, checkpoint_satisfied_count, pending_count


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--counts", action="store_true",
                        help="print: total metric_completed checkpoint_satisfied pending")
    parser.add_argument("ledger", type=Path)
    args = parser.parse_args()
    total, completed, satisfied, pending = validate(args.ledger)
    if args.counts:
        print(total, completed, satisfied, pending)
    else:
        print(
            "CHECKPOINT_ACTION_LEDGER=PASS metric_completed=%d "
            "checkpoint_satisfied=%d pending=%d total=%d"
            % (completed, satisfied, pending, total)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
