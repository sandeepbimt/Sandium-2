#!/usr/bin/env python3
"""Assert that FAST and FULL share SHE and failed builds cannot hand off."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / ".circleci" / "config.yml"

def main():
    text = CONFIG.read_text(encoding="utf-8")
    required = [
        "REMOTE_SMOKE=WARNING",
        "continuing to the real APK build under -strict_remote",
        "REMOTE_SMOKE=(PASS|WARNING|SKIPPED_VALID_APK)",
        "run_brave_build()",
        '2>&1 | tee "$log_file"',
        "PIPESTATUS[@]",
        "sandium-self-heal.py",
        "SHE_CLASSIFICATION",\n        "FEATURE_SUPPRESSION_MISSING_GENERATED_JAVA",\n        "REPAIR_WALLET_JAVA_COMPILE_CONTRACT",\n        "apply-sandium-wallet-java-compile-contract.py",\n        "REPAIR_WALLET_JAVA_COMPILE_CONTRACT",
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
            raise SystemExit("BRAVE_BUILD_FLOW_TEST=FAIL missing: " + token)
    forbidden = [
        "BUILD_REASON=ACTION_FAILED_HANDOFF",
        "BUILD_HANDOFF_ALLOWED=true\n              echo",
        "BRAVE_BUILD=SKIPPED remote worker smoke did not pass",
        "action-ledger.json",
    ]
    for token in forbidden:
        if token in text:
            raise SystemExit("BRAVE_BUILD_FLOW_TEST=FAIL unsafe/obsolete flow remains: " + token)
    print("BRAVE_BUILD_FLOW_TEST=PASS both modes use SHE; hard failures fail the build task; FULL checkpoint preservation remains unconditional")

if __name__ == "__main__":
    main()
