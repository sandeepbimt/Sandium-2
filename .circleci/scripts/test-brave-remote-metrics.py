#!/usr/bin/env python3
"""Regression tests for proof of fresh Siso remote execution."""
from __future__ import annotations
import json
from pathlib import Path
import subprocess
import sys
import tempfile

CHECKER = Path(__file__).with_name("verify-brave-remote-metrics.py")

def row(step: str, *, remote: bool, cached: bool = False, no_exec: bool = False, err: bool = False):
    return {"step_id": step, "is_remote": remote, "is_local": not remote,
            "cached": cached, "no_exec": no_exec, "err": err}

def run(path: Path, expected: int = 0) -> str:
    proc = subprocess.run([sys.executable, str(CHECKER), str(path)],
                          text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if proc.returncode != expected:
        raise AssertionError("expected exit=%d got=%d\n%s" % (expected, proc.returncode, proc.stdout))
    return proc.stdout

def main():
    with tempfile.TemporaryDirectory(prefix="sandium-remote-metrics-test-") as tmp:
        path = Path(tmp) / "smoke.jsonl"
        path.write_text("\n".join([
            json.dumps(row("cached-remote", remote=True, cached=True)),
            json.dumps(row("local-action", remote=False)),
            json.dumps(row("non-executing-handler", remote=True, no_exec=True)),
            json.dumps(row("fresh-remote", remote=True, cached=False)),
        ]) + "\n", encoding="utf-8")
        output = run(path)
        assert "BRAVE_REMOTE_EXECUTION_GATE=PASS fresh_remote_actions=1 remote_cache_hits=1" in output, output

        path.write_text("\n".join([
            json.dumps(row("only-cache", remote=True, cached=True)),
            json.dumps(row("only-local", remote=False)),
        ]) + "\n", encoding="utf-8")
        output = run(path, expected=2)
        assert "no fresh remote worker execution" in output, output
        audit = subprocess.run([sys.executable, str(CHECKER), "--audit", str(path)],
                               text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        assert audit.returncode == 3, audit.stdout
        assert "BRAVE_REMOTE_EXECUTION_GATE=WARNING no fresh remote worker execution" in audit.stdout, audit.stdout

        path.write_text(json.dumps(row("remote-failed", remote=True, err=True)) + "\n", encoding="utf-8")
        output = run(path, expected=2)
        assert "failed action records" in output, output

    print("BRAVE_REMOTE_METRICS_SELF_TEST=PASS cache hits are not accepted as worker execution")

if __name__ == "__main__":
    main()
