#!/usr/bin/env python3
"""Guard the Stage-1 flow so a smoke warning never suppresses APK compilation."""
from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / ".circleci" / "config.yml"

def main() -> None:
    from flow_wiring import verify_full_wiring
    verify_full_wiring(ROOT)
    text = CONFIG.read_text(encoding="utf-8")
    for name in ("remote-smoke.sh", "full-bounded-build.sh"):
        assert name in text, f"Full config must invoke {name}"
        text += "\n" + (ROOT / ".circleci/experimental-steps" / name).read_text(encoding="utf-8")
    required = [
        "REMOTE_SMOKE=WARNING",
        "continuing to the real APK build under -strict_remote",
        "if ! grep -Eq '^REMOTE_SMOKE=(PASS|WARNING|SKIPPED_VALID_APK)$'",
        'autoninja -strict_remote -metrics_json "$METRICS_FILE"',
        'verify-brave-remote-metrics.py" --audit "$OUT/$METRICS_FILE"',
        "REMOTE_EXECUTION_AUDIT=$REMOTE_EXECUTION_AUDIT",
    ]
    for token in required:
        if token not in text:
            raise SystemExit("BRAVE_BUILD_FLOW_TEST=FAIL missing: %s" % token)
    forbidden = [
        "BRAVE_BUILD=SKIPPED remote worker smoke did not pass",
        "BUILD_REASON=REMOTE_SMOKE_FAILED",
        "brave-action-ledger.py",
        "validate-brave-action-ledger.py",
        "action-ledger.json",
        "Plan exact pending Brave actions",
        "Reconcile Siso action metrics with the remaining action frontier",
        "ACTION_LEDGER",
    ]
    for token in forbidden:
        if token in text:
            raise SystemExit("BRAVE_BUILD_FLOW_TEST=FAIL obsolete smoke hard-stop remains: %s" % token)
    print("BRAVE_BUILD_FLOW_TEST=PASS smoke warnings do not suppress strict-remote APK compilation")

if __name__ == "__main__":
    main()
