#!/usr/bin/env python3
"""Require at least one fresh Siso action executed on a remote worker."""
from __future__ import annotations
import json
import sys
from pathlib import Path

def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: verify-brave-remote-metrics.py METRICS.jsonl")
    path = Path(sys.argv[1])
    if not path.is_file() or path.stat().st_size == 0:
        raise SystemExit("BRAVE_REMOTE_EXECUTION_GATE=FAIL missing or empty Siso metrics: %s" % path)

    fresh_remote = 0
    remote_cache_hits = 0
    local = 0
    failures = 0
    action_records = 0
    with path.open(encoding="utf-8", errors="replace") as stream:
        for number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SystemExit("BRAVE_REMOTE_EXECUTION_GATE=FAIL invalid JSON %s:%d: %s" %
                                 (path, number, exc))
            if not isinstance(row, dict) or not row.get("step_id"):
                continue
            action_records += 1
            failed = any(row.get(key) is True for key in ("err", "scandeps_err", "deps_log_err"))
            if failed:
                failures += 1
                continue
            if row.get("is_remote") is True:
                if row.get("cached") is True:
                    remote_cache_hits += 1
                elif row.get("no_exec") is not True:
                    fresh_remote += 1
            elif row.get("is_local") is True:
                local += 1

    if failures:
        raise SystemExit("BRAVE_REMOTE_EXECUTION_GATE=FAIL smoke metrics contain %d failed action records" % failures)
    if not action_records:
        raise SystemExit("BRAVE_REMOTE_EXECUTION_GATE=FAIL no per-action Siso metrics were recorded")
    if fresh_remote < 1:
        raise SystemExit("BRAVE_REMOTE_EXECUTION_GATE=FAIL no fresh remote worker execution; "
                         "remote_cache_hits=%d local_actions=%d action_records=%d" %
                         (remote_cache_hits, local, action_records))
    print("BRAVE_REMOTE_EXECUTION_GATE=PASS fresh_remote_actions=%d remote_cache_hits=%d "
          "local_actions=%d action_records=%d" %
          (fresh_remote, remote_cache_hits, local, action_records))

if __name__ == "__main__":
    main()
