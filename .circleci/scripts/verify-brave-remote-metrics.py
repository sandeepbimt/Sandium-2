#!/usr/bin/env python3
"""Require at least one fresh Siso action executed on a remote worker."""
from __future__ import annotations
import json
import sys
from pathlib import Path

def fail(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(2)

def main() -> None:
    audit = len(sys.argv) == 3 and sys.argv[1] == "--audit"
    if audit:
        path_arg = sys.argv[2]
    elif len(sys.argv) == 2:
        path_arg = sys.argv[1]
    else:
        fail("usage: verify-brave-remote-metrics.py [--audit] METRICS.jsonl")
    path = Path(path_arg)
    if not path.is_file() or path.stat().st_size == 0:
        fail("BRAVE_REMOTE_EXECUTION_GATE=FAIL missing or empty Siso metrics: %s" % path)

    fresh_remote = 0
    remote_cache_hits = 0
    local = 0
    failures = 0
    action_records = 0
    libchrome_link_records = 0
    libchrome_link_nonremote = 0
    with path.open(encoding="utf-8", errors="replace") as stream:
        for number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                fail("BRAVE_REMOTE_EXECUTION_GATE=FAIL invalid JSON %s:%d: %s" %
                     (path, number, exc))
            if not isinstance(row, dict) or not row.get("step_id"):
                continue
            action_records += 1
            outputs = row.get("outputs")
            if not isinstance(outputs, list):
                outputs = []
            is_libchrome_link = (
                row.get("action") == "solink" and
                any(str(output).endswith("/libchrome.so") or str(output) == "libchrome.so"
                    for output in outputs)
            )
            if is_libchrome_link:
                libchrome_link_records += 1
                if row.get("is_remote") is not True and row.get("cached") is not True:
                    libchrome_link_nonremote += 1
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

    if libchrome_link_nonremote:
        fail("BRAVE_LINK_REMOTE_GATE=FAIL libchrome.so SOLINK was executed locally in %d record(s); "
             "check -config googlechrome,remote-link" % libchrome_link_nonremote)
    if libchrome_link_records:
        print("BRAVE_LINK_REMOTE_GATE=PASS libchrome_solink_records=%d local_executions=0" %
              libchrome_link_records)
    else:
        print("BRAVE_LINK_REMOTE_GATE=NOT_APPLICABLE libchrome.so was not scheduled in this stage")
    if failures:
        fail("BRAVE_REMOTE_EXECUTION_GATE=FAIL smoke metrics contain %d failed action records" % failures)
    if not action_records:
        fail("BRAVE_REMOTE_EXECUTION_GATE=FAIL no per-action Siso metrics were recorded")
    if fresh_remote < 1:
        message = ("BRAVE_REMOTE_EXECUTION_GATE=WARNING no fresh remote worker execution observed; "
                   "remote_cache_hits=%d local_actions=%d action_records=%d" %
                   (remote_cache_hits, local, action_records))
        if audit:
            print(message)
            raise SystemExit(3)
        fail(message.replace("GATE=WARNING", "GATE=FAIL"))
    print("BRAVE_REMOTE_EXECUTION_GATE=PASS fresh_remote_actions=%d remote_cache_hits=%d "
          "local_actions=%d action_records=%d" %
          (fresh_remote, remote_cache_hits, local, action_records))

if __name__ == "__main__":
    main()
