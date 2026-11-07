#!/usr/bin/env python3
"""Guard the Stage-1 flow so a smoke warning never suppresses APK compilation."""
from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / ".circleci" / "config.yml"

def main() -> None:
    text = CONFIG.read_text(encoding="utf-8")
    required = [
        "REMOTE_SMOKE=WARNING",
        "continuing to the real APK build under -strict_remote",
        "if ! grep -Eq '^REMOTE_SMOKE=(PASS|WARNING|SKIPPED_VALID_APK)
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
",
        "run_brave_build()",
        '2>&1 | tee "$log_file"',
        'PIPESTATUS[@]',
        "sandium-self-heal.py",
        "SHE_CLASSIFICATION",
        "BUILD_HANDOFF_ALLOWED=false",
        "SANDIUM_SHE=FAIL",
        "SHE - enforce build outcome before stage continuation",
        "when: always",
        'verify-brave-remote-metrics.py" --audit "$OUT/$CURRENT_METRICS_FILE"',
        "REMOTE_EXECUTION_AUDIT=$REMOTE_EXECUTION_AUDIT",
        "full) STAGE_BUILD_BUDGET_SECONDS=1200",
        "fast) STAGE_BUILD_BUDGET_SECONDS=2700",
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
