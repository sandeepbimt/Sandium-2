#!/usr/bin/env python3
"""Sandium Self-Heal Engine: fail-closed build classification."""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path

INFRA = [
    re.compile(r"spawn-helper:.*(connection reset by peer|broken pipe|unexpected EOF)", re.I),
    re.compile(r"unknown service google[.]longrunning[.]Operations", re.I),
    re.compile(r"code = (DeadlineExceeded|Unavailable|ResourceExhausted|Aborted)", re.I),
    re.compile(r"Infra failure: .*remote-exec", re.I),
    re.compile(r"rpc error: code = (Unavailable|DeadlineExceeded|ResourceExhausted|Aborted)", re.I),
    re.compile(r"transport is closing|connection reset by peer", re.I),
]
CAS = re.compile(r"rpc error: code = FailedPrecondition desc = download inputs: could not (fetch inputs|get input tree): Digest hash:.*not found", re.I)
AI_CHAT = re.compile(r"(?:incomplete type|invalid application of .sizeof.)[^\n]{0,240}(?:TabDataWebContentsObserver|WebMcpInjector)|(?:TabDataWebContentsObserver|WebMcpInjector)[^\n]{0,240}incomplete type", re.I)
HARD = [
    re.compile(r"^\s*FAILED:\s+", re.M),
    re.compile(r"ninja: build stopped:|subcommand failed", re.I),
    re.compile(r"(?:^|:\s)(?:fatal\s+)?error:\s+", re.I | re.M),
    re.compile(r"undefined reference to|ld\.lld:\s*error:|collect2:\s*error:", re.I),
    re.compile(r"ERROR at [^\n]+\.gn", re.I),
    re.compile(r"Traceback \(most recent call last\):", re.I),
    re.compile(r"\bSISO_ACTION_FAILED\b|\bFAILED_TARGET\b", re.I),
]
FEATURE_SUPPRESSION_MISSING_GENERATED = re.compile(r"(?:symbol not found|could not resolve|cannot find symbol)[^\\n]{0,260}(?:org\\.chromium\\.brave_wallet\\.mojom\\.|decentralized_dns\\.(?:ResolveMethodTypes|EnsOffchainResolveMethod))|(?:org\\.chromium\\.brave_wallet\\.mojom\\.|decentralized_dns\\.(?:ResolveMethodTypes|EnsOffchainResolveMethod))[^\\n]{0,260}(?:symbol not found|could not resolve|cannot find symbol)", re.I)
OOM = re.compile(r"out of memory|oom-kill|killed process|signal 9|exit code 137", re.I)

def read(path, limit=8 * 1024 * 1024):
    if not path or not Path(path).is_file():
        return ""
    with open(path, "rb") as f:
        return f.read(limit).decode("utf-8", "replace")

def metric_errors(path):
    if not path or not Path(path).is_file():
        return []
    errors = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for n, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                errors.append("invalid Siso metrics JSON line %d" % n)
                continue
            if isinstance(row, dict) and row.get("step_id") and any(row.get(k) is True for k in ("err", "scandeps_err", "deps_log_err")):
                errors.append("Siso failed action metric line %d" % n)
    return errors

def classify(a):
    log = read(a.log)
    timed_out = a.exit_code == 124 and a.elapsed >= max(0, a.budget - 5)
    clean_lines = []
    for line in log.splitlines():
        if any(p.search(line) for p in INFRA):
            continue
        if timed_out and re.search(r"ninja: build stopped: interrupted by user", line, re.I):
            continue
        clean_lines.append(line)
    clean = "\n".join(clean_lines)
    targets = [x.strip() for x in read(a.failed_targets).splitlines() if x.strip() and not x.lstrip().startswith("#")]
    commands = bool(read(a.failed_commands).strip())
    metric = metric_errors(a.metrics)
    hard = [p.pattern for p in HARD if p.search(clean)]
    ai = bool(AI_CHAT.search(clean))\n    feature_suppression_missing_generated = bool(FEATURE_SUPPRESSION_MISSING_GENERATED.search(clean))
    cas = bool(CAS.search(log))
    infra = any(p.search(log) for p in INFRA)
    oom = bool(OOM.search(log))
    evidence = hard + metric
    if targets: evidence.append("Siso failed-targets file is non-empty")
    if commands: evidence.append("Siso failed-commands file is non-empty")
    if oom: evidence.append("OOM/killed-process signature")

    if ai and (hard or a.exit_code != 0):
        state, category, action = "FAILURE", "AI_CHAT_INCOMPLETE_TYPE", "REAPPLY_AI_CHAT_ANDROID_GUARDS"
    elif feature_suppression_missing_generated and (hard or a.exit_code != 0):
        state, category, action = "FAILURE", "FEATURE_SUPPRESSION_MISSING_GENERATED_JAVA", "DIAGNOSE_FEATURE_SUPPRESSION_GN_DEPS"
    elif cas and a.exit_code != 0:
        state, category, action = "RETRYABLE_INFRA", "MISSING_CAS_INPUTS", "RECOVER_CAS_INPUTS"
    elif evidence:
        state, category, action = "FAILURE", ("OOM" if oom else "BUILD_ACTION_FAILURE"), "NONE"
    elif infra and a.exit_code != 0:
        state, category, action = "RETRYABLE_INFRA", "REMOTE_TRANSPORT", "RETRY_REMOTE_REDUCED"
    elif a.exit_code == 124 and a.elapsed >= max(0, a.budget - 5):
        state, category, action = "TIME_SLICE_COMPLETE", "BOUNDED_TIMEOUT", "NONE"
    elif a.exit_code == 0:
        state, category, action = "SUCCESS", "BUILD_COMMAND_SUCCESS", "NONE"
    else:
        state, category, action = "FAILURE", "UNCLASSIFIED_NONZERO_EXIT", "NONE"
    return {
        "classification": state, "category": category, "repair_action": action,
        "exit_code": a.exit_code, "elapsed_seconds": a.elapsed, "budget_seconds": a.budget,
        "evidence": evidence[:20], "failed_target_count": len(targets),
        "failed_commands_present": commands, "metrics_failure_count": len(metric),
        "build_handoff_allowed": state in ("SUCCESS", "TIME_SLICE_COMPLETE"),
    }

def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("classify")
    for name in ("log", "metrics", "failed-targets", "failed-commands"):
        c.add_argument("--" + name)
    c.add_argument("--exit-code", type=int, required=True)
    c.add_argument("--elapsed", type=int, required=True)
    c.add_argument("--budget", type=int, required=True)
    c.add_argument("--result-file", required=True)
    g = sub.add_parser("gate")
    g.add_argument("--status-file", required=True)
    a = p.parse_args()
    if a.cmd == "classify":
        result = classify(a)
        Path(a.result_file).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print("SANDIUM_SHE_CLASSIFICATION=%s category=%s action=%s exit=%s" % (result["classification"], result["category"], result["repair_action"], result["exit_code"]))
        for item in result["evidence"]:
            print("SANDIUM_SHE_EVIDENCE=" + item, file=sys.stderr)
    else:
        path = Path(a.status_file)
        if not path.is_file():
            raise SystemExit("SANDIUM_SHE_GATE=FAIL build status missing")
        values = dict(line.split("=", 1) for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if "=" in line)
        state = values.get("SHE_CLASSIFICATION", "")
        allowed = values.get("BUILD_HANDOFF_ALLOWED", "")
        if state not in ("SUCCESS", "TIME_SLICE_COMPLETE") or allowed != "true":
            raise SystemExit("SANDIUM_SHE_GATE=FAIL classification=%s handoff_allowed=%s" % (state or "missing", allowed or "missing"))
        print("SANDIUM_SHE_GATE=PASS classification=" + state)

if __name__ == "__main__":
    main()
