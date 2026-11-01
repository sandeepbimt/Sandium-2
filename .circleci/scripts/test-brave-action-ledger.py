#!/usr/bin/env python3
"""Small integration test for brave-action-ledger.py's 88/100 -> 12/12 math."""
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
        assert "ACTION_HANDOFF_GATE=PASS pending=100/100" in plan1, plan1

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
                stream.write(json.dumps(row) + "\\n")
            for i in range(1000, 1010):
                stream.write(json.dumps(metric(i)) + "\\n")
        write_metrics(stage1_metrics, range(8, 88))
        done1 = run(["complete", *common, "--stage", "1", "--build", "101",
                     "--workflow", "workflow-one",
                     "--metrics-prefix", "test-stage1-"], env)
        assert "ACTION_REMOTE_SMOKE_RECONCILIATION=PASS planned_overlap=8 preflight_only=10" in done1, done1
        assert "ACTION_COMPLETION_MATH=PASS before=100 new=88 after=12" in done1, done1
        assert "SANDIUM_BUILD_MATH=88/100 complete; 12/12 pending" in done1, done1

        # The Stage 2 preflight must reject a replay-sized graph before compile.
        pending_file.write_text(json.dumps(list(range(100))), encoding="utf-8")
        wrong_plan = run(["plan", *common, "--stage", "2", "--build", "202",
                          "--workflow", "workflow-two"], env, expected=2)
        assert "ACTION_REEXECUTION_GATE=FAIL" in wrong_plan, wrong_plan

        pending_file.write_text(json.dumps(list(range(88, 100))), encoding="utf-8")
        plan2 = run(["plan", *common, "--stage", "2", "--build", "202",
                     "--workflow", "workflow-two"], env)
        assert "SANDIUM_BUILD_MATH=88/100 complete; 12/12 pending" in plan2, plan2

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
        pending_file.write_text("[]", encoding="utf-8")
        duplicate = run(["complete", *common, "--stage", "2", "--build", "202",
                         "--workflow", "workflow-two",
                         "--metrics-prefix", "test-stage2-"], env, expected=2)
        assert "ACTION_REEXECUTION_GATE=FAIL" in duplicate, duplicate

        # Correct handoff: exactly the 12 previously unfinished actions.
        write_metrics(stage2_metrics, range(88, 100))
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
        done2 = run(["complete", *common, "--stage", "2", "--build", "202",
                     "--workflow", "workflow-two",
                     "--metrics-prefix", "test-stage2-"], env)
        assert "ACTION_COMPLETION_MATH=PASS before=12 new=12 after=0" in done2, done2
        assert "SANDIUM_BUILD_MATH=100/100 complete; 0/0 pending" in done2, done2
        assert "SANDIUM_ACTION_FRONTIER=COMPLETE total=100" in done2, done2

    print("BRAVE_ACTION_LEDGER_SELF_TEST=PASS 88/100 -> 12/12 -> 100/100")

if __name__ == "__main__":
    main()
