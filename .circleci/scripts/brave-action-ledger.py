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

SCHEMA = 2
PROGRESS = re.compile(r"\[(\d+)\s*/\s*(\d+)\]")

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

def dry_run_actions(autoninja: Path, src: Path, out: Path, jobs: int,
                    stage: int, build: str, workflow: str) -> tuple[set[str], dict]:
    # Siso dry-run writes one StepMetric JSONL row for every planned action.
    # The visible [x/y] progress is an independent cross-check on metric
    # coverage; we never substitute the display counter for action identities.
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", f"{workflow}-{build}-stage-{stage}")
    metrics_name = f".sandium-action-plan-{safe}.jsonl"
    metrics_path = out / metrics_name
    metrics_path.unlink(missing_ok=True)
    cmd = [str(autoninja), "-strict_remote", "-n", "-metrics_json",
           metrics_name, "-C", str(out), f"-j{jobs}", "brave"]
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
        tail, no_work = [], False
        progress_ordinals, progress_denominators = set(), set()
        for line in log:
            line = line.rstrip("\r\n")
            if line:
                tail.append(line)
                tail = tail[-20:]
            if "no work to do" in line.lower():
                no_work = True
            for match in PROGRESS.finditer(line):
                progress_ordinals.add(int(match.group(1)))
                progress_denominators.add(int(match.group(2)))
        if rc:
            die("ACTION_PLAN_DRY_RUN=FAIL autoninja returned %d\n%s" %
                (rc, "\n".join(tail)))
    actions, stats = read_metrics(out, "__no_plan_metrics_prefix__", [metrics_path])
    if stats["failed_records"]:
        die("ACTION_PLAN_DRY_RUN=FAIL dry-run metrics contain %d failed action records" %
            stats["failed_records"])
    keys = set(actions)
    if progress_denominators:
        displayed_total = max(progress_denominators)
        displayed_last = max(progress_ordinals) if progress_ordinals else 0
        if displayed_total != len(keys):
            die("ACTION_PLAN_METRIC_COVERAGE=FAIL Siso dry-run denominator=%d but unique action identities=%d; "
                "refusing to start compilation" % (displayed_total, len(keys)))
        if displayed_last != displayed_total:
            die("ACTION_PLAN_METRIC_COVERAGE=FAIL Siso dry-run reached ordinal=%d of %d but captured %d action identities" %
                (displayed_last, displayed_total, len(keys)))
    elif keys:
        # Siso may suppress the progress UI in non-interactive output. The
        # metric set remains authoritative, but record this for audit.
        displayed_total, displayed_last = None, None
    else:
        displayed_total, displayed_last = 0, 0
    if not keys:
        if no_work and stats["action_records"] == 0:
            metrics_path.unlink(missing_ok=True)
            return set(), {"metrics_file": metrics_name, "metrics": stats,
                           "no_work": True, "progress_denominators": [],
                           "displayed_last_ordinal": 0}
        die("ACTION_PLAN_DRY_RUN=FAIL Siso dry-run did not emit per-action metrics; "
            "cannot produce an exact pending action set. Output tail:\n%s" %
            "\n".join(tail))
    metrics_path.unlink(missing_ok=True)
    manifest_stub = bool(keys and len(keys) <= 2 and not progress_denominators)
    return keys, {"metrics_file": metrics_name, "metrics": stats,
                  "no_work": False, "action_count": len(keys),
                  "manifest_stub": manifest_stub,
                  "progress_denominators": sorted(progress_denominators),
                  "displayed_last_ordinal": displayed_last}



def load(path: Path):
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        die(f"ACTION_LEDGER_READ=FAIL {path}: {e}")
    if not isinstance(data.get("completed"), dict):
        die("ACTION_LEDGER_SCHEMA=FAIL invalid completed map")
    if data.get("schema_version") == 1 and not data.get("next_pending_action_keys"):
        # Schema 1 tracked counts and metric keys but did not persist the exact
        # pending action set. It cannot be upgraded by assuming its counts were
        # correct. Stage 1 will reconstruct the ledger from retained Siso logs.
        print("ACTION_LEDGER_MIGRATION=REBUILD_FROM_RETAINED_METRICS schema=1", file=sys.stderr)
        return None
    if data.get("schema_version") != SCHEMA:
        die("ACTION_LEDGER_SCHEMA=FAIL unsupported schema %r" % data.get("schema_version"))
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
    outputs = sorted({x.replace("\\\\", "/") for x in outputs if isinstance(x, str) and x})
    digest, cmdhash = str(row.get("digest") or ""), str(row.get("cmdhash") or "")
    rule, action = str(row.get("rule") or ""), str(row.get("action") or "")
    if cmdhash:
        # Preserve execution-specific command/digest data for audit, but keep
        # the ledger key independent of execution mode. Siso dry-run records
        # can be marked no_exec and omit cmdhash, while the matching real
        # execution record includes cmdhash. Both must identify the same Ninja
        # work unit across the pre-build plan and post-build reconciliation.
        ident = {"step_id": step_id, "outputs": outputs, "cmdhash": cmdhash,
                 "rule": rule, "action": action, "action_digest": digest,
                 "mode": "ninja-step-output"}
    elif row.get("no_exec") is True:
        ident = {"outputs": outputs, "step_id": step_id, "rule": rule,
                 "action": action, "mode": "no-exec-step"}
    else:
        die(f"ACTION_METRICS_SCHEMA=FAIL step_id={step_id!r} missing cmdhash")
    stable = {"step_id": step_id, "outputs": outputs,
              "rule": rule, "action": action}
    key = sha(json.dumps(stable, sort_keys=True, separators=(",", ":")).encode())
    return key, ident

def read_metrics(out: Path, prefix: str, extra_files=()):
    actions, stats = {}, {"files": [], "records": 0, "action_records": 0,
                          "summary_records": 0, "failed_records": 0,
                          "duplicate_records": 0,
                          "successful_duplicate_records": 0}
    # The remote-worker smoke test has its own target and its own
    # metrics file. Do not mix that sidecar graph into the main APK target's
    # action set; complete() reads the smoke file separately and credits only
    # smoke actions that overlap the APK plan.
    files = {p for p in out.glob(prefix + "*.jsonl")
             if p.is_file() and not p.name.endswith("smoke.jsonl")}
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
                    stats["duplicate_records"] += int(key in actions)
                    actions[key] = {"success": False, "identity": ident}
                    continue
                if key in actions:
                    stats["duplicate_records"] += 1
                    if actions[key].get("success"):
                        stats["successful_duplicate_records"] += 1
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
    pending_keys, dry = dry_run_actions(autoninja, src, out, a.jobs,
                                             a.stage, a.build, a.workflow)
    pending = len(pending_keys)
    run_id = f"{a.workflow}:{a.build}:stage-{a.stage}"

    if a.phase == "plan":
        if ledger is None:
            if a.stage != 1:
                die("ACTION_LEDGER_BOOTSTRAP=FAIL stage >1 has no persisted action ledger")
            # Preserve every restored object/generated output. Do not infer
            # historical completion from object counts or incomplete old
            # metrics. The live Siso dry-run is the exact residual-work
            # baseline; all earlier restored outputs are outside this ledger.
            ledger = {"schema_version": SCHEMA, "identity": ident,
                      "baseline_scope": "remaining_actions_at_restored_checkpoint",
                      "planned_total": pending, "completed": {}, "stages": [],
                      "next_pending_action_keys": sorted(pending_keys),
                      "legacy_seed": {"historical_object_files_excluded": True,
                                      "historical_metrics_used": False,
                                      "restored_object_file_count": len(list((out / "obj").rglob("*.o"))) if (out / "obj").is_dir() else 0},
                      "created_at_epoch": int(time.time())}
            print("ACTION_LEDGER_BOOTSTRAP=PASS scope=remaining-work pending=%d total=%d historical_objects_preserved=true" %
                  (pending, pending))
        elif ledger.get("identity", {}).get("fingerprint") != ident.get("fingerprint"):
            die("ACTION_LEDGER_IDENTITY=FAIL build graph/source/config fingerprint changed")
        active_before = ledger.get("active_stage")
        if active_before and active_before.get("run_id") != run_id:
            die("ACTION_LEDGER_RECOVERY=FAIL unfinished prior stage %s; do not overwrite its action frontier" %
                active_before.get("run_id"))
        # If a previously completed output was removed (for example, a restored
        # APK failed ZIP/signature/package validation), Siso's live dry-run puts
        # that action back into the pending set. Reopen only those exact action
        # identities; do not infer or reopen unrelated work.
        reopened = set(pending_keys).intersection(ledger.get("completed", {}))
        if reopened:
            invalidation_marker = src.parent / ".sandium" / "invalid-apk-output-for-ledger"
            if not invalidation_marker.is_file():
                die("ACTION_REEXECUTION_GATE=FAIL %d previously completed action(s) are pending again without an explicit invalid-APK recovery marker" % len(reopened))
            apk_action_keys = set()
            for key in reopened:
                identity = ledger["completed"][key].get("identity", {})
                outputs = identity.get("outputs", [])
                step_id = str(identity.get("step_id", ""))
                if any("BraveMonoarm64.apk" in str(output) for output in outputs) or "BraveMonoarm64.apk" in step_id:
                    apk_action_keys.add(key)
            if apk_action_keys != reopened:
                die("ACTION_REEXECUTION_GATE=FAIL invalid-APK marker may reopen only the APK-producing action; unrelated completed actions reappeared=%d" %
                    len(reopened - apk_action_keys))
            for key in reopened:
                ledger["completed"].pop(key, None)
            ledger.setdefault("invalidated_action_reopens", []).append({
                "stage_run": run_id, "action_keys": sorted(reopened),
                "reason": "APK preflight removed an invalid BraveMonoarm64.apk output",
                "recorded_at_epoch": int(time.time())})
            ledger["next_pending_action_keys"] = sorted(
                set(ledger.get("next_pending_action_keys", [])) | reopened)
            invalidation_marker.unlink(missing_ok=True)
            print("ACTION_INVALIDATED_APK_ACTION_REOPENED=%d" % len(reopened))
        total, done = int(ledger["planned_total"]), len(ledger["completed"])
        expected = total - done
        if expected < 0:
            die(f"ACTION_LEDGER_STATE=FAIL completed={done} total={total}")
        if pending != expected:
            die("ACTION_HANDOFF_GATE=FAIL expected_pending=%d dry_run_pending=%d completed=%d total=%d; "
                "stopping before compilation" % (expected, pending, done, total))
        expected_keys = set(ledger.get("next_pending_action_keys", []))
        if expected_keys != pending_keys:
            added = sorted(pending_keys - expected_keys)
            missing = sorted(expected_keys - pending_keys)
            die("ACTION_HANDOFF_SET_GATE=FAIL pending action identity set changed; "
                "new=%d missing=%d examples_new=%s examples_missing=%s" %
                (len(added), len(missing), added[:5], missing[:5]))
        ledger["active_stage"] = {"run_id": run_id, "workflow": a.workflow,
                                  "build": a.build, "stage": a.stage,
                                  "pending_before": pending, "pending_action_keys": sorted(pending_keys),
                                  "completed_before": done, "planned_total": total,
                                  "dry_run": dry, "planned_at_epoch": int(time.time())}
        save(path, ledger)
        print(f"ACTION_HANDOFF_GATE=PASS pending={pending}/{expected}")
        print(f"SANDIUM_BUILD_MATH={done}/{total} complete; {pending}/{expected} pending")
        print(f"ACTION_PLAN_DRY_RUN=PASS action_identities={pending} progress_denominators={dry.get('progress_denominators')}")
        return

    if ledger is None or ledger.get("identity", {}).get("fingerprint") != ident.get("fingerprint"):
        die("ACTION_LEDGER_IDENTITY=FAIL missing ledger or graph/source/config changed")
    active = ledger.get("active_stage") or {}
    if active.get("run_id") != run_id:
        die(f"ACTION_LEDGER_STAGE=FAIL active={active.get('run_id')} current={run_id}")
    # Main APK-target metrics and the remote preflight smoke metrics are
    # separate accounting domains. The smoke probe intentionally invokes an
    # additional Perfetto host-tool target; those sidecar-only actions must not
    # be treated as unplanned APK compilation. However, any smoke actions that
    # are also in the APK target's pre-build frontier are genuine completed APK
    # prerequisites and must be credited to avoid a false pending-set mismatch.
    metrics, stats = read_metrics(out, a.metrics_prefix)
    smoke_path = out / f"{a.metrics_prefix}smoke.jsonl"
    smoke_metrics, smoke_stats = read_metrics(
        out, "__sandium_no_smoke_prefix__", [smoke_path])
    if stats["successful_duplicate_records"]:
        die("ACTION_DUPLICATE_WITHIN_STAGE=FAIL %d APK-build actions were successfully recorded more than once in this stage" %
            stats["successful_duplicate_records"])
    if smoke_stats["successful_duplicate_records"]:
        die("ACTION_SMOKE_DUPLICATE=FAIL %d smoke actions were successfully recorded more than once" %
            smoke_stats["successful_duplicate_records"])
    if stats["failed_records"] or smoke_stats["failed_records"]:
        die("ACTION_METRICS_FAILURE=FAIL apk_build_failed_records=%d remote_smoke_failed_records=%d" %
            (stats["failed_records"], smoke_stats["failed_records"]))
    pending_before_keys = set(active.get("pending_action_keys", []))
    if len(pending_before_keys) != int(active.get("pending_before", -1)):
        die("ACTION_LEDGER_STAGE=FAIL missing or invalid pending action identity set")
    smoke_planned = {key: item for key, item in smoke_metrics.items()
                     if key in pending_before_keys}
    smoke_preflight_only = set(smoke_metrics) - pending_before_keys
    duplicate_smoke_build = set(smoke_planned).intersection(metrics)
    if duplicate_smoke_build:
        die("ACTION_DUPLICATE_ACROSS_SMOKE_AND_BUILD=FAIL %d planned actions were recorded by both the smoke probe and APK build" %
            len(duplicate_smoke_build))
    metrics = {**smoke_planned, **metrics}
    print("ACTION_REMOTE_SMOKE_RECONCILIATION=PASS planned_overlap=%d preflight_only=%d failed_records=%d" %
          (len(smoke_planned), len(smoke_preflight_only), smoke_stats["failed_records"]))
    if not stats["files"] and not smoke_planned and int(active.get("pending_before", 0)):
        die(f"ACTION_METRICS_MISSING=FAIL no APK-build metrics or planned smoke-overlap metrics found for prefix {a.metrics_prefix}")
    previous = ledger["completed"]
    revisited = set(metrics).intersection(previous)
    if revisited:
        die(f"ACTION_REEXECUTION_GATE=FAIL {len(revisited)} previously completed actions appeared again")

    # Siso's real execution can discover additional actions after the dry-run
    # frontier was captured (for example, generated/dynamic dependency work).
    # Reconcile three independent sets:
    #   P = pending action identities recorded before compilation
    #   M = successful action identities reported by Siso during this stage
    #   A = identities still pending in a fresh post-build dry-run
    #
    # A planned action must either be in M or remain in A. Every successful
    # action in M must be absent from A. New actions in M-P are counted as
    # dynamically discovered completed work; new actions in A-P are added to
    # the persistent pending frontier. This preserves exact accounting without
    # rejecting legitimate Siso graph discovery or weakening duplicate checks.
    before = len(pending_before_keys)
    after_keys, after_dry = dry_run_actions(
        autoninja, src, out, a.jobs, a.stage, a.build, a.workflow)
    planned_completed_keys = set(metrics).intersection(pending_before_keys)
    dynamically_completed_keys = set(metrics) - pending_before_keys
    planned_remaining_keys = pending_before_keys - planned_completed_keys
    still_pending_planned_keys = after_keys.intersection(pending_before_keys)
    newly_pending_keys = after_keys - pending_before_keys

    # A metric must never claim that an action completed while the same action
    # remains pending in the live Siso graph.
    metric_still_pending = set(metrics).intersection(after_keys)
    if metric_still_pending:
        die("ACTION_METRIC_STILL_PENDING=FAIL %d successful action(s) remain pending after execution; examples=%s" %
            (len(metric_still_pending), sorted(metric_still_pending)[:5]))

    # A verified APK is the deliverable. Siso can prune stale planned nodes
    # when its graph is re-evaluated after compilation. Do not call those nodes
    # "completed": record them as pruned and remove them from the denominator,
    # but only when the live graph is fully closed and the APK has passed every
    # archive/signature/package check. If work remains or the APK is invalid,
    # retain the strict frontier failure.
    apk = out / "apks" / "BraveMonoarm64.apk"
    marker = src.parent / ".sandium" / "apk-completion-status.txt"
    required = {
        "BUILD_FINISHED=true",
        "APK_ARCHIVE_VALID=true",
        "APK_SIGNATURE_VALID=true",
        "APK_PACKAGE_ID_VALID=true",
    }
    marker_lines = set(marker.read_text(encoding="utf-8").splitlines()) if marker.is_file() else set()
    apk_validated = apk.is_file() and apk.stat().st_size > 0 and required.issubset(marker_lines)

    vanished = planned_remaining_keys - still_pending_planned_keys
    unexpected = still_pending_planned_keys - planned_remaining_keys
    if unexpected:
        die("ACTION_PLANNED_FRONTIER_MISMATCH=FAIL unexpected_planned_pending=%d examples=%s" %
            (len(unexpected), sorted(unexpected)[:5]))
    pruned_planned_keys = set()
    pruned_reason = None
    handoff_pending_keys = set(after_keys)
    if vanished:
        initial_dry = active.get("dry_run") or {}
        build_status_path = src.parent / ".sandium" / "build-stage-status.txt"
        build_status = {}
        if build_status_path.is_file():
            for line in build_status_path.read_text(encoding="utf-8", errors="replace").splitlines():
                if "=" in line:
                    key, value = line.split("=", 1)
                    build_status[key.strip()] = value.strip()
        time_slice_complete = (
            build_status.get("BUILD_REASON") == "TIME_SLICE_COMPLETE" and
            build_status.get("BUILD_EXIT_CODE") in {"124", "130"}
        )
        if time_slice_complete and not after_keys and not apk_validated:
            # A deliberate timeout can leave Siso's post-build -n probe
            # temporarily reporting an empty graph even though the original
            # planned frontier was not accounted for by successful metrics.
            # Never relabel those actions as completed or pruned. Preserve
            # their exact identities for the next stage, whose fresh -n probe
            # must reproduce this frontier before any compilation is allowed.
            handoff_pending_keys = set(planned_remaining_keys) | set(newly_pending_keys)
            print("ACTION_TIME_SLICE_FRONTIER_PRESERVED=PASS "
                  "planned_remaining=%d dynamic_pending=%d live_post_build_pending=%d "
                  "next_stage_must_revalidate=true" %
                  (len(planned_remaining_keys), len(newly_pending_keys), len(after_keys)))
        initial_action_count = int(initial_dry.get("action_count", before))
        after_action_count = int(after_dry.get("action_count", len(after_keys)))
        # Before its first real invocation, Siso can expose only the two
        # manifest/bootstrap nodes to a -n metrics probe. The first real build
        # then rebuilds the manifest and expands the graph into actual actions.
        provisional_manifest = bool(
            initial_dry.get("manifest_stub") or
            (initial_action_count <= 2 and not initial_dry.get("progress_denominators"))
        )
        expanded_live_graph = (
            provisional_manifest and
            after_action_count >= max(32, initial_action_count * 10) and
            (bool(dynamically_completed_keys) or bool(newly_pending_keys))
        )
        if expanded_live_graph:
            pruned_planned_keys = set(vanished)
            pruned_reason = "provisional_manifest_nodes_superseded_by_expanded_siso_graph"
            print("ACTION_PRUNED_MANIFEST_STUB=PASS count=%d initial_actions=%d expanded_pending=%d "
                  "dynamically_completed=%d; reason=%s" %
                  (len(pruned_planned_keys), initial_action_count, after_action_count,
                   len(dynamically_completed_keys), pruned_reason))
        elif time_slice_complete and not after_keys and not apk_validated:
            # handled above: retain the unaccounted planned actions as pending
            # rather than treating graph disappearance as successful completion.
            pass
        elif not after_keys and apk_validated:
            pruned_planned_keys = set(vanished)
            pruned_reason = "stale_plan_nodes_absent_from_closed_graph_with_verified_apk"
            print("ACTION_PRUNED_STALE_PLAN=PASS count=%d; reason=%s" %
                  (len(pruned_planned_keys), pruned_reason))
        else:
            die("ACTION_PLANNED_FRONTIER_MISMATCH=FAIL planned_not_completed=%d but_still_pending=%d "
                "unaccounted_vanished=%d apk_validated=%s initial_plan_actions=%d expanded_pending=%d "
                "manifest_stub=%s examples_vanished=%s examples_pending=%s" %
                (len(planned_remaining_keys), len(still_pending_planned_keys),
                 len(vanished), apk_validated, initial_action_count, after_action_count,
                 provisional_manifest, sorted(vanished)[:5], sorted(still_pending_planned_keys)[:5]))
        planned_remaining_keys -= pruned_planned_keys
        ledger["planned_total"] = int(ledger["planned_total"]) - len(pruned_planned_keys)
        if ledger["planned_total"] < len(ledger["completed"]):
            die("ACTION_PRUNED_ACCOUNTING=FAIL pruned actions would make completed exceed planned total")

    # A previously completed action must not reappear in the next frontier.
    reappeared = after_keys.intersection(previous)
    if reappeared:
        die("ACTION_REEXECUTION_PENDING=FAIL %d previously completed action(s) reappeared in the post-build frontier; examples=%s" %
            (len(reappeared), sorted(reappeared)[:5]))

    added = len(metrics)
    if before > 0 and added == 0 and not newly_pending_keys and len(after_keys) == before:
        die("ACTION_STAGE_NO_PROGRESS=FAIL this stage completed zero new actions and left the pending frontier unchanged")

    # Newly discovered work is part of the build denominator, not an error.
    # Completed discoveries increase both total and completed; still-pending
    # discoveries increase total and remain in the next stage's exact frontier.
    newly_accounted = len(dynamically_completed_keys) + len(newly_pending_keys)
    ledger["planned_total"] = int(ledger["planned_total"]) + newly_accounted
    now = int(time.time())
    for key, item in metrics.items():
        ledger["completed"][key] = {
            "identity": item["identity"], "completed_by": run_id,
            "completed_at_epoch": now, "cached": item["cached"],
            "is_remote": item["is_remote"], "is_local": item["is_local"],
            "no_exec": item["no_exec"]}
    ledger["stages"].append({
        "run_id": run_id, "stage": a.stage,
        "pending_before": before,
        "planned_completed": len(planned_completed_keys),
        "dynamically_completed": len(dynamically_completed_keys),
        "pruned_from_final_graph": len(pruned_planned_keys),
        "pruned_action_keys": sorted(pruned_planned_keys),
        "pruned_reason": pruned_reason,
        "newly_pending": len(newly_pending_keys),
        "newly_discovered_action_keys": sorted(dynamically_completed_keys | newly_pending_keys),
        "new_completed": added,
        "pending_after": len(handoff_pending_keys),
        "metric_stats": stats,
        "after_dry_run": after_dry,
        "completed_total": len(ledger["completed"]),
        "planned_total_after": ledger["planned_total"],
        "recorded_at_epoch": now})
    ledger["next_pending_action_keys"] = sorted(handoff_pending_keys)
    ledger.pop("active_stage", None)
    total, done = int(ledger["planned_total"]), len(ledger["completed"])
    after = len(handoff_pending_keys)
    remaining = total - done
    if remaining != after:
        die("ACTION_COMPLETION_MATH=FAIL total=%d completed=%d ledger_remaining=%d live_pending=%d" %
            (total, done, remaining, after))
    save(path, ledger)
    print("ACTION_FRONTIER_RECONCILIATION=PASS planned_completed=%d dynamically_completed=%d newly_pending=%d pending_after=%d" %
          (len(planned_completed_keys), len(dynamically_completed_keys),
           len(newly_pending_keys), after))
    print("ACTION_DYNAMIC_ACTION_ACCOUNTING=PASS discovered_completed=%d discovered_pending=%d" %
          (len(dynamically_completed_keys), len(newly_pending_keys)))
    print(f"ACTION_COMPLETION_MATH=PASS before={before} new={added} after={after}")
    print(f"ACTION_METRICS=PASS files={len(stats['files'])} records={stats['records']} "
          f"actions={stats['action_records']} unique={added} failed_records={stats['failed_records']}")
    print(f"SANDIUM_BUILD_MATH={done}/{total} complete; {remaining}/{remaining} pending")
    if remaining == 0:
        if apk_validated:
            ledger["build_complete"] = True
            ledger["completed_at_epoch"] = now
            save(path, ledger)
            print(f"SANDIUM_ACTION_FRONTIER=COMPLETE total={total} apk_validated=true")
        else:
            # All current graph actions have completed, but the APK did not
            # pass validation. Save this closed frontier; the next stage's APK
            # preflight removes the invalid output and plan() will reopen only
            # the exact actions Siso says are pending again.
            ledger["build_complete"] = False
            ledger["apk_validation_pending"] = True
            save(path, ledger)
            print("SANDIUM_ACTION_FRONTIER=GRAPH_COMPLETE_APK_UNVALIDATED; next stage may reopen invalidated APK actions")
    else:
        print(f"SANDIUM_ACTION_FRONTIER=CONTINUE remaining={remaining}; next stage must dry-run to exactly {remaining}")

if __name__ == "__main__":
    main()
