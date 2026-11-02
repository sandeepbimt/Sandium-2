#!/usr/bin/env python3
"""Regression test for dynamic Siso action discovery and staged frontier handoff."""
from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

SCRIPT = Path(__file__).with_name("brave-action-ledger.py")

def run(args, env, expected=0):
    p = subprocess.run([sys.executable, str(SCRIPT), *args], env=env,
                       text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if p.returncode != expected:
        raise AssertionError(f"expected exit={expected}, got={p.returncode}\n{p.stdout}")
    return p.stdout

def metric(i):
    return {
        "step_id": f"//obj/action-{i:03d}.o",
        "rule": "cxx", "action": "compile",
        "outputs": [f"obj/action-{i:03d}.o"],
        "cmdhash": f"cmdhash-{i:03d}",
        "digest": f"sha256:{i:064x}",
        "is_remote": True, "is_local": False,
        "cached": False, "no_exec": False, "err": False,
    }

def write_metrics(path, ids):
    with path.open("w", encoding="utf-8") as f:
        for i in ids:
            f.write(json.dumps(metric(i)) + "\n")

def git(repo: Path, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

def main():
    with tempfile.TemporaryDirectory(prefix="sandium-ledger-test-") as temp:
        root = Path(temp)
        src = root / "brave-work" / "src"
        core = src / "brave"
        out = src / "out" / "android_Release_arm64"
        files = [
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
        for path in files:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("stable test content\n", encoding="utf-8")
        for repo in (src, core):
            git(repo, "init")
            git(repo, "config", "user.email", "ledger-test@example.invalid")
            git(repo, "config", "user.name", "Ledger Test")
            git(repo, "add", "-A")
            git(repo, "commit", "-m", "fixture")
        git(core, "tag", "v1.98.62")

        autoninja = root / "autoninja"
        autoninja.write_text("""#!/usr/bin/env python3
import json
import os
import pathlib
import sys

args = sys.argv[1:]
out = pathlib.Path(args[args.index("-C") + 1])
metrics = args[args.index("-metrics_json") + 1]
ids = json.loads(pathlib.Path(os.environ["LEDGER_TEST_PENDING_IDS"]).read_text())
if "-n" in args:
    path = out / metrics
    with path.open("w", encoding="utf-8") as f:
        for i in ids:
            row = {
                "step_id": f"//obj/action-{i:03d}.o",
                "rule": "cxx",
                "action": "compile",
                "outputs": [f"obj/action-{i:03d}.o"],
                # Siso dry-run records may omit execution-only hashes.
                # The ledger key must still match the later real action row.
                "is_remote": False,
                "is_local": False,
                "cached": False,
                "no_exec": True,
                "err": False,
            }
            f.write(json.dumps(row) + "\\n")
    if not ids:
        print("ninja: no work to do.")
    elif os.environ.get("LEDGER_TEST_MANIFEST_STUB") == "1":
        print("schedule pending:1+ready:0 (node:161001 edge:2)")
    else:
        for i in range(1, len(ids) + 1):
            print(f"[{i}/{len(ids)}] dry-run action")
        print(f"DRY_RUN_PENDING_ACTIONS={len(ids)}")
""", encoding="utf-8")
        autoninja.chmod(0o755)
        pending_file = root / "pending_ids.json"
        env = os.environ.copy()
        env["LEDGER_TEST_PENDING_IDS"] = str(pending_file)

        common = ["--src", str(src), "--out", str(out),
                  "--autoninja", str(autoninja), "--jobs", "80"]

        pending_file.write_text(json.dumps(list(range(100))), encoding="utf-8")
        out.mkdir(parents=True, exist_ok=True)
        out.mkdir(parents=True, exist_ok=True)
        plan1 = run(["plan", *common, "--stage", "1", "--build", "101",
                     "--workflow", "workflow-one"], env)
        assert "ACTION_HANDOFF_GATE=PASS live_siso_pending=100/100" in plan1, plan1

        stage1_metrics = out / "test-stage1-0.jsonl"
        write_metrics(stage1_metrics, range(88))
        # Simulate the remote smoke target and main build both executing the
        # same successful work unit in one stage: never silently deduplicate.
        with stage1_metrics.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(metric(0)) + "\n")
        pending_file.write_text(json.dumps(list(range(88, 100))), encoding="utf-8")
        duplicate_stage = run(["complete", *common, "--stage", "1", "--build", "101",
                               "--workflow", "workflow-one",
                               "--metrics-prefix", "test-stage1-"], env, expected=2)
        assert "ACTION_DUPLICATE_WITHIN_STAGE=FAIL" in duplicate_stage, duplicate_stage
        # The Perfetto remote-worker smoke target is a sidecar graph. Eight
        # smoke actions overlap the APK plan and count as completed APK work;
        # unrelated smoke-only actions must not poison APK reconciliation.
        smoke_metrics = out / "test-stage1-smoke.jsonl"
        with smoke_metrics.open("w", encoding="utf-8") as stream:
            for i in range(8):
                row = metric(i)
                row.pop("cmdhash")
                row.pop("digest")
                row["no_exec"] = True
                stream.write(json.dumps(row) + "\n")
            for i in range(1000, 1010):
                stream.write(json.dumps(metric(i)) + "\n")
        write_metrics(stage1_metrics, range(8, 88))
        # Siso may emit real build actions that were not visible in the initial
        # dry-run. Mirror the recurring 65-action failure and require those
        # successful actions to be added to the denominator, not rejected.
        with stage1_metrics.open("a", encoding="utf-8") as stream:
            for i in range(2000, 2065):
                stream.write(json.dumps(metric(i)) + "\n")
        done1 = run(["complete", *common, "--stage", "1", "--build", "101",
                     "--workflow", "workflow-one",
                     "--metrics-prefix", "test-stage1-"], env)
        assert "ACTION_REMOTE_SMOKE_RECONCILIATION=PASS planned_overlap=8 preflight_only=10" in done1, done1
        assert "ACTION_FRONTIER_RECONCILIATION=PASS planned_completed=88 dynamically_completed=65 newly_pending=0 pending_after=12" in done1, done1
        assert "ACTION_DYNAMIC_ACTION_ACCOUNTING=PASS discovered_completed=65 discovered_pending=0" in done1, done1
        assert "ACTION_COMPLETION_MATH=PASS before=100 new=153 after=12" in done1, done1
        assert "SANDIUM_BUILD_MATH=metric_completed=153 checkpoint_satisfied=0 pending=12 total=165" in done1, done1

        # The Stage 2 preflight must reject a replay-sized graph before compile.
        pending_file.write_text(json.dumps(list(range(100))), encoding="utf-8")
        wrong_plan = run(["plan", *common, "--stage", "2", "--build", "202",
                          "--workflow", "workflow-two"], env, expected=2)
        assert "ACTION_REEXECUTION_GATE=FAIL" in wrong_plan, wrong_plan

        pending_file.write_text(json.dumps(list(range(88, 100))), encoding="utf-8")
        plan2 = run(["plan", *common, "--stage", "2", "--build", "202",
                     "--workflow", "workflow-two"], env)
        assert "SANDIUM_BUILD_MATH=metric_completed=153 checkpoint_satisfied=0 pending=12 total=165" in plan2, plan2

        # A previously completed action must not execute again.
        stage2_metrics = out / "test-stage2-0.jsonl"
        duplicate_action = metric(0)
        # Same output + command, but a different input action digest must still
        # be recognized as the same logical work unit and rejected.
        duplicate_action["digest"] = "sha256:" + ("f" * 64)
        duplicate_action["cmdhash"] = "different-execution-mode-command-hash"
        rows = [duplicate_action, *(metric(i) for i in range(88, 99))]
        with stage2_metrics.open("w", encoding="utf-8") as stream:
            for row in rows:
                stream.write(json.dumps(row) + "\n")
        # Simulate Siso discovering three additional pending actions after the timed slice.
        pending_file.write_text(json.dumps(list(range(2003, 2006))), encoding="utf-8")
        duplicate = run(["complete", *common, "--stage", "2", "--build", "202",
                         "--workflow", "workflow-two",
                         "--metrics-prefix", "test-stage2-"], env, expected=2)
        assert "ACTION_REEXECUTION_GATE=FAIL" in duplicate, duplicate

        # A build can discover one additional completed action and a further
        # pending action after the original dry-run. Both must be accounted for:
        # the completed action expands total+completed; the pending action
        # expands total+remaining and must be handed to Stage 3.
        write_metrics(stage2_metrics, range(88, 99))
        with stage2_metrics.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(metric(3000)) + "\n")
        pending_file.write_text(json.dumps([99, 4000, 4001]), encoding="utf-8")
        dynamic = run(["complete", *common, "--stage", "2", "--build", "202",
                       "--workflow", "workflow-two",
                       "--metrics-prefix", "test-stage2-"], env)
        assert "ACTION_FRONTIER_RECONCILIATION=PASS planned_completed=11 dynamically_completed=1 newly_pending=2 pending_after=3" in dynamic, dynamic
        assert "ACTION_DYNAMIC_ACTION_ACCOUNTING=PASS discovered_completed=1 discovered_pending=2" in dynamic, dynamic
        assert "SANDIUM_BUILD_MATH=metric_completed=165 checkpoint_satisfied=0 pending=3 total=168" in dynamic, dynamic

        # The next stage must receive the exact augmented frontier, including
        # newly discovered action 4000, and complete the original final action.
        stage3_plan = run(["plan", *common, "--stage", "3", "--build", "303",
                           "--workflow", "workflow-three"], env)
        assert "ACTION_HANDOFF_GATE=PASS live_siso_pending=3/3" in stage3_plan, stage3_plan
        stage3_metrics = out / "test-stage3-0.jsonl"
        write_metrics(stage3_metrics, [99])
        pending_file.write_text("[]", encoding="utf-8")
        (out / "apks").mkdir(parents=True, exist_ok=True)
        (out / "apks" / "BraveMonoarm64.apk").write_bytes(b"test-apk")
        marker = src.parent / ".sandium" / "apk-completion-status.txt"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(
            "BUILD_FINISHED=true\n"
            "APK_ARCHIVE_VALID=true\n"
            "APK_SIGNATURE_VALID=true\n"
            "APK_PACKAGE_ID_VALID=true\n",
            encoding="utf-8")
        done3 = run(["complete", *common, "--stage", "3", "--build", "303",
                     "--workflow", "workflow-three",
                     "--metrics-prefix", "test-stage3-"], env)
        assert "ACTION_PRUNED_STALE_PLAN=PASS count=2; reason=stale_plan_nodes_absent_from_closed_graph_with_verified_apk" in done3, done3
        assert "ACTION_COMPLETION_MATH=PASS before=3 new=1 after=0" in done3, done3
        assert "SANDIUM_BUILD_MATH=metric_completed=166 checkpoint_satisfied=0 pending=0 total=166" in done3, done3
        assert "SANDIUM_ACTION_FRONTIER=COMPLETE total=166" in done3, done3

        # Regression for build 675: the first -n probe saw only two Siso
        # manifest/bootstrap nodes. The real time-sliced build expanded the
        # graph, completed 60 actions and left 40 for the next stage. Those
        # provisional nodes must be pruned without requiring the APK first.
        (src.parent / ".sandium" / "action-ledger.json").unlink()
        pending_file.write_text(json.dumps([9000, 9001]), encoding="utf-8")
        env["LEDGER_TEST_MANIFEST_STUB"] = "1"
        stub_plan = run(["plan", *common, "--stage", "1", "--build", "404",
                         "--workflow", "manifest-stub-workflow"], env)
        assert "ACTION_PLAN_DRY_RUN=PASS action_identities=2 progress_denominators=[]" in stub_plan, stub_plan
        env["LEDGER_TEST_MANIFEST_STUB"] = "0"
        manifest_metrics = out / "test-manifest-stage1-0.jsonl"
        write_metrics(manifest_metrics, range(10000, 10060))
        pending_file.write_text(json.dumps(list(range(11000, 11040))), encoding="utf-8")
        manifest_done = run(["complete", *common, "--stage", "1", "--build", "404",
                             "--workflow", "manifest-stub-workflow",
                             "--metrics-prefix", "test-manifest-stage1-"], env)
        assert "ACTION_PRUNED_MANIFEST_STUB=PASS count=2 initial_actions=2 expanded_pending=40 dynamically_completed=60" in manifest_done, manifest_done
        assert "ACTION_FRONTIER_RECONCILIATION=PASS planned_completed=0 dynamically_completed=60 newly_pending=40 pending_after=40" in manifest_done, manifest_done
        assert "ACTION_COMPLETION_MATH=PASS before=2 new=60 after=40" in manifest_done, manifest_done
        assert "SANDIUM_BUILD_MATH=metric_completed=60 checkpoint_satisfied=0 pending=40 total=100" in manifest_done, manifest_done

        # Regression: a deliberate 15-minute build slice may leave the
        # post-build Siso dry-run empty even though the pre-build frontier was
        # not fully accounted for. Preserve those exact planned identities as
        # pending; the next stage must reproduce them before it may compile.
        (src.parent / ".sandium" / "action-ledger.json").unlink()
        # This fixture must not inherit the verified APK marker created by
        # the earlier APK-gated pruning test; otherwise the production-safe
        # stale-plan pruning branch correctly takes precedence.
        stale_marker = src.parent / ".sandium" / "apk-completion-status.txt"
        stale_marker.unlink(missing_ok=True)
        stale_apk = out / "apks" / "BraveMonoarm64.apk"
        stale_apk.unlink(missing_ok=True)
        status_path = src.parent / ".sandium" / "build-stage-status.txt"
        status_path.parent.mkdir(parents=True, exist_ok=True)
        status_path.write_text(
            "BUILD_EXIT_CODE=137\nBUILD_REASON=TIME_SLICE_COMPLETE\nBUILD_TIME_SLICE_EXPIRED=true\n",
            encoding="utf-8")
        pending_file.write_text(json.dumps(list(range(20))), encoding="utf-8")
        slice_plan = run(["plan", *common, "--stage", "1", "--build", "505",
                          "--workflow", "time-slice-workflow"], env)
        assert "ACTION_HANDOFF_GATE=PASS live_siso_pending=20/20" in slice_plan, slice_plan
        slice_metrics = out / "test-timeslice-stage1-0.jsonl"
        write_metrics(slice_metrics, range(8))
        with slice_metrics.open("a", encoding="utf-8") as stream:
            for i in range(2000, 2003):
                stream.write(json.dumps(metric(i)) + "\n")
        pending_file.write_text(json.dumps(list(range(2003, 2006))), encoding="utf-8")
        slice_done = run(["complete", *common, "--stage", "1", "--build", "505",
                          "--workflow", "time-slice-workflow",
                          "--metrics-prefix", "test-timeslice-stage1-"], env)
        assert "ACTION_TIME_SLICE_FRONTIER_PRESERVED=PASS planned_remaining=12 dynamic_pending=3 live_post_build_pending=3" in slice_done, slice_done
        assert "ACTION_FRONTIER_RECONCILIATION=PASS planned_completed=8 dynamically_completed=3 newly_pending=3 pending_after=15" in slice_done, slice_done
        assert "SANDIUM_BUILD_MATH=metric_completed=11 checkpoint_satisfied=0 pending=15 total=26" in slice_done, slice_done

        # The next stage is allowed to continue only if its fresh Siso dry-run
        # reconstructs the exact 12-action frontier from the saved checkpoint.
        pending_file.write_text(json.dumps(list(range(8, 20)) + list(range(2003, 2006))), encoding="utf-8")
        slice_stage2 = run(["plan", *common, "--stage", "2", "--build", "506",
                            "--workflow", "time-slice-next"], env)
        assert "ACTION_HANDOFF_GATE=PASS live_siso_pending=15/15" in slice_stage2, slice_stage2
        assert "SANDIUM_BUILD_MATH=metric_completed=11 checkpoint_satisfied=0 pending=15 total=26" in slice_stage2, slice_stage2


        # A restored checkpoint can make many previously pending actions
        # disappear from the live Siso dry-run without producing fresh metric
        # rows. They must be classified separately, not treated as completed
        # metrics and not allowed to block the next compilation slice.
        (src.parent / ".sandium" / "action-ledger.json").unlink(missing_ok=True)
        (src.parent / ".sandium" / "apk-completion-status.txt").unlink(missing_ok=True)
        (out / "apks" / "BraveMonoarm64.apk").unlink(missing_ok=True)
        pending_file.write_text(json.dumps(list(range(100))), encoding="utf-8")
        restored_plan1 = run(["plan", *common, "--stage", "1", "--build", "606",
                              "--workflow", "restored-state-workflow"], env)
        assert "ACTION_HANDOFF_GATE=PASS live_siso_pending=100/100" in restored_plan1, restored_plan1
        restored_stage1_metrics = out / "test-restored-stage1-0.jsonl"
        write_metrics(restored_stage1_metrics, range(20))
        pending_file.write_text(json.dumps(list(range(20, 100))), encoding="utf-8")
        restored_done1 = run(["complete", *common, "--stage", "1", "--build", "606",
                              "--workflow", "restored-state-workflow",
                              "--metrics-prefix", "test-restored-stage1-"], env)
        assert "SANDIUM_BUILD_MATH=metric_completed=20 checkpoint_satisfied=0 pending=80 total=100" in restored_done1, restored_done1

        # A second invocation sees only 30 of the prior 80 pending actions.
        # The other 50 are already satisfied by the restored Siso/output state.
        pending_file.write_text(json.dumps(list(range(20, 50))), encoding="utf-8")
        restored_plan2 = run(["plan", *common, "--stage", "2", "--build", "607",
                              "--workflow", "restored-state-next"], env)
        assert "ACTION_CHECKPOINT_RECONCILIATION=PASS resolved_by_restored_state=50 reopened=0 new_pending=0 previous_total=100 reconciled_total=100" in restored_plan2, restored_plan2
        assert "SANDIUM_BUILD_MATH=metric_completed=20 checkpoint_satisfied=50 pending=30 total=100" in restored_plan2, restored_plan2

        restored_stage2_metrics = out / "test-restored-stage2-0.jsonl"
        write_metrics(restored_stage2_metrics, range(20, 30))
        pending_file.write_text(json.dumps(list(range(30, 50))), encoding="utf-8")
        restored_done2 = run(["complete", *common, "--stage", "2", "--build", "607",
                              "--workflow", "restored-state-next",
                              "--metrics-prefix", "test-restored-stage2-"], env)
        assert "SANDIUM_BUILD_MATH=metric_completed=30 checkpoint_satisfied=50 pending=20 total=100" in restored_done2, restored_done2

    print("BRAVE_ACTION_LEDGER_SELF_TEST=PASS dynamic discovery + pending handoff + APK-gated pruning + manifest-stub expansion + bounded-slice recovery")

if __name__ == "__main__":
    main()
