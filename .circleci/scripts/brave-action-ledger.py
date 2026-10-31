#!/usr/bin/env python3
"""Action-level continuation checks for Sandium's pinned Brave Android build.

The Siso [x/y] display is invocation-local. This ledger uses:
  * an autoninja/Siso dry-run to count the exact pending target actions;
  * Siso JSONL metrics (outputs + cmdhash + digest) to identify completed actions;
  * a graph/config fingerprint to bind the ledger to one immutable build;
  * before/after reconciliation so completed + remaining must equal prior pending.

The first ledger-managed stage establishes the denominator from the pending work
at that checkpoint. Later stages and workflows keep that denominator unchanged.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCHEMA = 1
PROGRESS = re.compile(r"^\s*\[(\d+)\s*/\s*(\d+)\]")

def die(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(2)

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def file_sha(path: Path) -> str:
    if not path.is_file():
        die(f"ACTION_LEDGER_IDENTITY=FAIL missing {path}")
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def git(src: Path, *args: str) -> str:
    p = subprocess.run(["git", "-C", str(src), *args], text=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode:
        die(f"ACTION_LEDGER_IDENTITY=FAIL git {' '.join(args)}: {p.stderr.strip()}")
    return p.stdout.strip()

def fingerprint(src: Path, out: Path) -> dict:
    core = src / "brave"
    paths = [
        out / "build.ninja", out / "args.gn", out / "args_generated.gni",
        src / "build/config/siso/.sisorc",
        src / "build/config/siso/.sisoenv",
        src / "build/config/siso/backend_config/backend.star",
        src / "build/config/siso/brave_siso_config.star",
        src / "build/config/compiler/compiler.gni",
        core / ".env",
        core / "third_party/reclient_configs/brave_custom/brave_custom.py",
        src / "buildtools/reclient_cfgs/python/python_remote_wrapper",
    ]
    hashes = {}
    for p in paths:
        name = str(p.relative_to(src)) if p.is_relative_to(src) else str(p)
        hashes[name] = file_sha(p) if p.is_file() else None
    result = {
        "target": "brave", "build_type": "Release",
        "target_os": "android", "target_arch": "arm64",
        "chromium_sha": git(src, "rev-parse", "HEAD"),
        "brave_tag": git(core, "describe", "--tags", "--exact-match"),
        "files": hashes,
    }
    result["fingerprint"] = sha(json.dumps(result, sort_keys=True,
                                            separators=(",", ":")).encode())
    return result

def dry_run_count(autoninja: Path, src: Path, out: Path, jobs: int) -> tuple[int, dict]:
    # Count the unique progress ordinals, not Siso's displayed denominator:
    # Siso may revise that denominator as it discovers/schedules dependencies.
    cmd = [str(autoninja), "-strict_remote", "-n", "-C", str(out),
           f"-j{jobs}", "brave"]
    env = os.environ.copy()
    env["SISO_LIMITS"] = "local=8,remote=80"
    with tempfile.TemporaryFile(mode="w+t", encoding="utf-8", errors="replace") as log:
        try:
            p = subprocess.Popen(cmd, cwd=str(src), env=env, stdout=log,
                                 stderr=subprocess.STDOUT, text=True)
            rc = p.wait(timeout=900)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait()
            die("ACTION_PLAN_DRY_RUN=FAIL timed out after 900 seconds")
        log.flush()
        log.seek(0)
        ordinals, denominators = set(), set()
        no_work = False
        tail = []
        for line in log:
            line = line.rstrip("\r\n")
            if line:
                tail.append(line)
                tail = tail[-10:]
            m = PROGRESS.match(line)
            if m:
                ordinals.add(int(m.group(1)))
                denominators.add(int(m.group(2)))
            if "no work to do" in line.lower():
                no_work = True
        if rc:
            die("ACTION_PLAN_DRY_RUN=FAIL autoninja returned %d\n%s" %
                (rc, "\n".join(tail)))
    if not ordinals:
        if no_work or not tail:
            return 0, {"progress_ordinals": 0, "display_denominators": []}
        die("ACTION_PLAN_DRY_RUN=FAIL unrecognised dry-run output; refusing to guess\n%s"
            % "\n".join(tail))
    maximum = max(ordinals)
    if min(ordinals) != 1 or len(ordinals) != maximum:
        die("ACTION_PLAN_DRY_RUN=FAIL non-contiguous progress ordinals "
            f"unique={len(ordinals)} max={maximum} denominators={sorted(denominators)}")
    return len(ordinals), {"progress_ordinals": len(ordinals),
                           "display_denominators": sorted(denominators)}

def load(path: Path):
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        die(f"ACTION_LEDGER_READ=FAIL {path}: {e}")
    if data.get("schema_version") != SCHEMA or not isinstance(data.get("completed"), dict):
        die("ACTION_LEDGER_SCHEMA=FAIL invalid schema/completed map")
    return data

def save(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".action-ledger.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, sort_keys=True, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def metric_key(row: dict):
    step_id = str(row.get("step_id") or "").strip()
    if not step_id:
        return None  # build-level summary record
    outputs = row.get("outputs")
    if not isinstance(outputs, list):
        output = row.get("output")
        outputs = [output] if isinstance(output, str) and output else []
    outputs = sorted({x.replace("\\", "/") for x in outputs if isinstance(x, str) and x})
    if not outputs and row.get("no_exec") is not True:
        die(f"ACTION_METRICS_SCHEMA=FAIL step_id={step_id!r} has no outputs and is not a no_exec handler")
    digest, cmdhash = str(row.get("digest") or ""), str(row.get("cmdhash") or "")
    rule, action = str(row.get("rule") or ""), str(row.get("action") or "")
    if cmdhash:
        # Digest binds the action to its current input Merkle tree and is kept
        # for audit, but it is intentionally not part of the logical work-unit
        # key. The same output/command must not become "new work" just because
        # a restored dependency digest changed between stages.
        ident = {"outputs": outputs, "cmdhash": cmdhash,
                 "rule": rule, "action": action, "action_digest": digest,
                 "mode": "command-output-action"}
        stable = {k: v for k, v in ident.items() if k != "action_digest"}
    elif row.get("no_exec") is True:
        ident = {"outputs": outputs, "step_id": step_id, "rule": rule,
                 "action": action, "mode": "no-exec-step"}
        stable = ident
    else:
        die(f"ACTION_METRICS_SCHEMA=FAIL step_id={step_id!r} missing cmdhash")
    key = sha(json.dumps(stable, sort_keys=True, separators=(",", ":")).encode())
    return key, ident

def read_metrics(out: Path, prefix: str, extra_files=()):
    actions, stats = {}, {"files": [], "records": 0, "action_records": 0,
                          "summary_records": 0, "failed_records": 0,
                          "duplicate_records": 0}
    files = {p for p in out.glob(prefix + "*.jsonl") if p.is_file()}
    files.update(p for p in extra_files if p.is_file())
    files = sorted(files)
    for path in files:
        if not path.stat().st_size:
            continue
        stats["files"].append(path.name)
        with path.open(encoding="utf-8", errors="replace") as f:
            for n, line in enumerate(f, 1):
                if not line.strip():
                    continue
                stats["records"] += 1
                try:
                    row = json.loads(line)
                except Exception as e:
                    die(f"ACTION_METRICS_JSONL=FAIL {path.name}:{n}: {e}")
                if not isinstance(row, dict):
                    die(f"ACTION_METRICS_JSONL=FAIL {path.name}:{n} not an object")
                result = metric_key(row)
                if result is None:
                    stats["summary_records"] += 1
                    continue
                stats["action_records"] += 1
                key, ident = result
                failed = any(row.get(k) is True for k in ("err", "scandeps_err", "deps_log_err"))
                if failed:
                    stats["failed_records"] += 1
                    if key not in actions:
                        actions[key] = {"success": False, "identity": ident}
                    continue
                if key in actions:
                    stats["duplicate_records"] += 1
                actions[key] = {
                    "success": True, "identity": ident,
                    "cached": bool(row.get("cached")),
                    "is_remote": bool(row.get("is_remote")),
                    "is_local": bool(row.get("is_local")),
                    "no_exec": bool(row.get("no_exec")),
                }
    return {k: v for k, v in actions.items() if v.get("success")}, stats

def normalize_output(path: str, out: Path) -> str:
    value = path.replace("\\", "/")
    if os.path.isabs(value):
        try:
            value = os.path.relpath(value, str(out)).replace("\\", "/")
        except ValueError:
            pass
    while value.startswith("./"):
        value = value[2:]
    return os.path.normpath(value).replace("\\", "/")


def ninja_log_outputs(out: Path) -> set[str]:
    log = out / ".ninja_log"
    if not log.is_file():
        return set()
    outputs = set()
    with log.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("#"):
                continue
            fields = line.rstrip("\r\n").split("\t")
            if len(fields) >= 4 and fields[3]:
                outputs.add(normalize_output(fields[3], out))
    return outputs


def metric_outputs(actions: dict, out: Path) -> set[str]:
    outputs = set()
    for item in actions.values():
        for value in item["identity"].get("outputs", []):
            outputs.add(normalize_output(value, out))
    return outputs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=["plan", "complete"])
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--autoninja", required=True)
    ap.add_argument("--stage", required=True, type=int)
    ap.add_argument("--build", required=True)
    ap.add_argument("--workflow", required=True)
    ap.add_argument("--jobs", type=int, default=80)
    ap.add_argument("--metrics-prefix", default="")
    a = ap.parse_args()
    src, out = Path(a.src).resolve(), Path(a.out).resolve()
    autoninja = Path(a.autoninja).resolve()
    path = src.parent / ".sandium" / "action-ledger.json"
    ident = fingerprint(src, out)
    ledger = load(path)
    pending, dry = dry_run_count(autoninja, src, out, a.jobs)
    run_id = f"{a.workflow}:{a.build}:stage-{a.stage}"

    if a.phase == "plan":
        if ledger is None:
            if a.stage != 1:
                die("ACTION_LEDGER_BOOTSTRAP=FAIL stage >1 has no persisted action ledger")
            # Siso's logWriter truncates the current metrics file and rotates
            # previous invocations to .1, .2, ... .9. Recover the legacy
            # action history from every retained rotation before establishing
            # the denominator for a checkpoint created before this ledger.
            legacy_files = []
            legacy_re = re.compile(r"^sandium-brave-siso-metrics(?:\.\d+)?\.json$")
            for candidate in out.glob("sandium-brave-siso-metrics*"):
                if candidate.is_file() and legacy_re.match(candidate.name):
                    legacy_files.append(candidate)
            seed_actions, seed_stats = read_metrics(out, "__no_legacy_seed_match__", legacy_files)
            object_files = list((out / "obj").rglob("*.o")) if (out / "obj").is_dir() else []
            if object_files and not seed_actions:
                die("ACTION_LEDGER_BOOTSTRAP=REFUSED legacy checkpoint has %d object files but no usable retained Siso action metrics; "
                    "cannot claim an exact completed/remaining denominator" % len(object_files))
            logged_outputs = ninja_log_outputs(out)
            covered_outputs = metric_outputs(seed_actions, out)
            uncovered = sorted(logged_outputs - covered_outputs)
            if uncovered:
                die("ACTION_LEDGER_BOOTSTRAP=REFUSED retained metrics do not cover %d outputs in .ninja_log; "
                    "old action history is incomplete (examples: %s)" %
                    (len(uncovered), ", ".join(uncovered[:8])))
            if object_files and not logged_outputs:
                die("ACTION_LEDGER_BOOTSTRAP=REFUSED object files exist but .ninja_log has no output records")
            seed_completed = {}
            for key, item in seed_actions.items():
                seed_completed[key] = {
                    "identity": item["identity"], "completed_by": "legacy-siso-metrics",
                    "completed_at_epoch": int(time.time()), "cached": item["cached"],
                    "is_remote": item["is_remote"], "is_local": item["is_local"],
                    "no_exec": item["no_exec"]}
            ledger = {"schema_version": SCHEMA, "identity": ident,
                      "baseline_scope": "retained_completed_actions_plus_current_pending_graph",
                      "planned_total": len(seed_completed) + pending,
                      "completed": seed_completed, "stages": [],
                      "legacy_seed": {"files": seed_stats["files"],
                                      "unique_completed_actions": len(seed_completed),
                                      "ninja_log_outputs": len(logged_outputs),
                                      "covered_ninja_log_outputs": len(logged_outputs)},
                      "created_at_epoch": int(time.time())}
            print("ACTION_LEDGER_BOOTSTRAP=PASS retained_completed=%d pending=%d total=%d metrics_files=%d" %
                  (len(seed_completed), pending, len(seed_completed) + pending, len(seed_stats["files"])))
        elif ledger.get("identity", {}).get("fingerprint") != ident.get("fingerprint"):
            die("ACTION_LEDGER_IDENTITY=FAIL build graph/source/config fingerprint changed")
        active_before = ledger.get("active_stage")
        if active_before and active_before.get("run_id") != run_id:
            die("ACTION_LEDGER_RECOVERY=FAIL unfinished prior stage %s; do not overwrite its action frontier" %
                active_before.get("run_id"))
        total, done = int(ledger["planned_total"]), len(ledger["completed"])
        expected = total - done
        if expected < 0:
            die(f"ACTION_LEDGER_STATE=FAIL completed={done} total={total}")
        if pending != expected:
            die("ACTION_HANDOFF_GATE=FAIL expected_pending=%d dry_run_pending=%d completed=%d total=%d; "
                "stopping before compilation" % (expected, pending, done, total))
        ledger["active_stage"] = {"run_id": run_id, "workflow": a.workflow,
                                  "build": a.build, "stage": a.stage,
                                  "pending_before": pending, "completed_before": done,
                                  "planned_total": total, "dry_run": dry,
                                  "planned_at_epoch": int(time.time())}
        save(path, ledger)
        print(f"ACTION_HANDOFF_GATE=PASS pending={pending}/{expected}")
        print(f"SANDIUM_BUILD_MATH={done}/{total} complete; {pending}/{expected} pending")
        print(f"ACTION_PLAN_DRY_RUN=PASS ordinals={pending} denominators={dry['display_denominators']}")
        return

    if ledger is None or ledger.get("identity", {}).get("fingerprint") != ident.get("fingerprint"):
        die("ACTION_LEDGER_IDENTITY=FAIL missing ledger or graph/source/config changed")
    active = ledger.get("active_stage") or {}
    if active.get("run_id") != run_id:
        die(f"ACTION_LEDGER_STAGE=FAIL active={active.get('run_id')} current={run_id}")
    metrics, stats = read_metrics(out, a.metrics_prefix)
    if not stats["files"] and int(active.get("pending_before", 0)):
        die(f"ACTION_METRICS_MISSING=FAIL no files match {a.metrics_prefix}*.jsonl")
    previous = ledger["completed"]
    revisited = set(metrics).intersection(previous)
    if revisited:
        die(f"ACTION_REEXECUTION_GATE=FAIL {len(revisited)} previously completed actions appeared again")
    before, added = int(active["pending_before"]), len(metrics)
    after, after_dry = dry_run_count(autoninja, src, out, a.jobs)
    if before > 0 and added == 0 and after == before:
        die("ACTION_STAGE_NO_PROGRESS=FAIL this stage completed zero new actions and left the pending frontier unchanged")
    if added + after != before:
        die("ACTION_COMPLETION_MATH=FAIL before=%d successful_new_actions=%d after=%d stats=%s dry=%s" %
            (before, added, after, json.dumps(stats, sort_keys=True), json.dumps(after_dry, sort_keys=True)))
    now = int(time.time())
    for key, item in metrics.items():
        ledger["completed"][key] = {
            "identity": item["identity"], "completed_by": run_id,
            "completed_at_epoch": now, "cached": item["cached"],
            "is_remote": item["is_remote"], "is_local": item["is_local"],
            "no_exec": item["no_exec"]}
    ledger["stages"].append({"run_id": run_id, "stage": a.stage,
                             "pending_before": before, "new_completed": added,
                             "pending_after": after, "metric_stats": stats,
                             "after_dry_run": after_dry,
                             "completed_total": len(ledger["completed"]),
                             "recorded_at_epoch": now})
    ledger.pop("active_stage", None)
    total, done = int(ledger["planned_total"]), len(ledger["completed"])
    if done > total:
        die(f"ACTION_LEDGER_OVERFLOW=FAIL completed={done} total={total}")
    save(path, ledger)
    remaining = total - done
    print(f"ACTION_COMPLETION_MATH=PASS before={before} new={added} after={after}")
    print(f"ACTION_METRICS=PASS files={len(stats['files'])} records={stats['records']} "
          f"actions={stats['action_records']} unique={added} failed_records={stats['failed_records']}")
    print(f"SANDIUM_BUILD_MATH={done}/{total} complete; {remaining}/{remaining} pending")
    if remaining == 0:
        apk = out / "apks" / "BraveMonoarm64.apk"
        if not apk.is_file() or not apk.stat().st_size:
            die("ACTION_LEDGER_FINAL=FAIL no work remains but BraveMonoarm64.apk is missing")
        ledger["build_complete"] = True
        ledger["completed_at_epoch"] = now
        save(path, ledger)
        print(f"SANDIUM_ACTION_FRONTIER=COMPLETE total={total}")
    else:
        print(f"SANDIUM_ACTION_FRONTIER=CONTINUE remaining={remaining}; next stage must dry-run to exactly {remaining}")

if __name__ == "__main__":
    main()
