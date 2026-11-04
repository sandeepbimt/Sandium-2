#!/usr/bin/env python3
"""Integration test for source-only Sandium checkpoint archive/restore."""
from __future__ import annotations
import importlib.util
import os
import subprocess
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).with_name("sandium-source-shards.py")
SPEC = importlib.util.spec_from_file_location("sandium_source_shards", SCRIPT)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)

def run(command: list[str], cwd: Path | None = None) -> str:
    result = subprocess.run(command, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise AssertionError("%s failed:\n%s\n%s" % (command, result.stdout, result.stderr))
    return result.stdout.strip()

with tempfile.TemporaryDirectory(prefix="sandium-source-checkpoint-test-") as temp:
    root = Path(temp)
    work = root / "brave-work"
    src = work / "src"
    core = src / "brave"
    out = src / "out" / "android_Release_arm64"

    (work / ".sandium").mkdir(parents=True)
    src.mkdir(parents=True)
    core.mkdir(parents=True)
    (src / "build").mkdir(parents=True)
    (src / "third_party" / "sample").mkdir(parents=True)
    (src / "buildtools" / "reclient_cfgs" / "python").mkdir(parents=True)
    (src / "build" / "config" / "siso" / "backend_config").mkdir(parents=True)
    (core / "node_modules" / ".pnpm").mkdir(parents=True)
    (out / "obj").mkdir(parents=True)

    (work / ".gclient").write_text('solutions = [{"name":"src"}]\n', encoding="utf-8")
    (work / ".gclient_entries").write_text("entries\n", encoding="utf-8")
    (src / "build" / "install-build-deps.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    (src / "third_party" / "sample" / "dep.txt").write_text("dependency\n", encoding="utf-8")
    (core / "package.json").write_text(
        '{"version":"1.99.54","config":{"projects":{"chrome":{"tag":"157.0.8103.30"}}}}\n',
        encoding="utf-8")
    (core / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n", encoding="utf-8")
    (core / "node_modules" / ".modules.yaml").write_text("layoutVersion: 9\n", encoding="utf-8")
    (src / "build" / "config" / "siso" / ".sisoenv").write_text("SISO_REAPI_ADDRESS=remote.buildbuddy.io:443\n", encoding="utf-8")
    (src / "build" / "config" / "siso" / ".sisorc").write_text("ninja -re_cache_enable_write=true\n", encoding="utf-8")
    (src / "build" / "config" / "siso" / "backend_config" / "backend.star").write_text("container_image = 'docker://test'\n", encoding="utf-8")
    (src / "build" / "config" / "siso" / "brave_siso_config.star").write_text('rule["canonicalize_dir"] = True\n"./args.gn"\n', encoding="utf-8")
    wrapper = src / "buildtools" / "reclient_cfgs" / "python" / "python_remote_wrapper"
    wrapper.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    wrapper.chmod(0o755)
    (out / "build.ninja").write_text("build all: phony\n", encoding="utf-8")
    (out / "args.gn").write_text('target_cpu = "arm64"\n', encoding="utf-8")
    (out / "args_generated.gni").write_text(
        "use_remoteexec = true\nuse_siso = true\nuse_reclient = false\n"
        "is_official_build = true\nandroid_aab_to_apk = true\n", encoding="utf-8")
    (out / "obj" / "example.o").write_bytes(b"compiled-object")
    (out / ".siso_fs_state").write_bytes(b"build-state")

    for marker in ("source-sync-complete", "source-runhooks-complete",
                   "source-configure-complete", "source-gn-complete"):
        (work / ".sandium" / marker).write_text("complete\n", encoding="utf-8")
    (work / ".sandium" / "source-prep-progress.txt").write_text(
        "STAGE=5\nPHASE=source-ready\nREFRESH_REQUEST_ID=unit-test\n", encoding="utf-8")

    run(["git", "init", str(src)])
    run(["git", "-C", str(src), "config", "user.email", "test@example.com"])
    run(["git", "-C", str(src), "config", "user.name", "Sandium Test"])
    (src / "README.md").write_text("chromium source\n", encoding="utf-8")
    run(["git", "-C", str(src), "add", "README.md"])
    run(["git", "-C", str(src), "commit", "-m", "test chromium source"])
    chromium_sha = run(["git", "-C", str(src), "rev-parse", "HEAD"])

    run(["git", "init", str(core)])
    run(["git", "-C", str(core), "config", "user.email", "test@example.com"])
    run(["git", "-C", str(core), "config", "user.name", "Sandium Test"])
    (core / "README.md").write_text("brave core\n", encoding="utf-8")
    run(["git", "-C", str(core), "add", "README.md", "package.json", "pnpm-lock.yaml"])
    run(["git", "-C", str(core), "commit", "-m", "test Brave Core"])
    run(["git", "-C", str(core), "tag", "v1.99.54"])
    brave_sha = run(["git", "-C", str(core), "rev-parse", "HEAD"])
    (work / ".sandium" / "source-pins.env").write_text(
        "BRAVE_CORE_TAG=v1.99.54\nBRAVE_CORE_SHA=%s\nCHROMIUM_TAG=157.0.8103.30\nCHROMIUM_SHA=%s\nREFRESH_REQUEST_ID=unit-test\n"
        % (brave_sha, "0" * 40),
        encoding="utf-8")

    # A timed-out gclient sync can leave a valid previous Chromium HEAD but a
    # different target SHA. Progress archives must remain resumable in that state.
    (work / ".sandium" / "source-prep-progress.txt").write_text(
        "STAGE=1\nPHASE=pinning-incomplete\nREFRESH_REQUEST_ID=unit-test\n", encoding="utf-8")
    module.archive(root, workers=2, stage=1, ready=False)
    progress = module.verify(root, workers=2, zstd_test=True, require_ready=False)
    assert progress["ready"] is False
    assert progress["source"]["chromium_sha"] == "0" * 40
    assert progress["source"]["actual_chromium_sha"] == chromium_sha
    assert progress["source"]["refresh_request_id"] == "unit-test"
    assert progress["source"]["pin_refresh_request_id"] == "unit-test"
    assert progress["source"]["brave_core_sha"] == brave_sha
    assert progress["source"]["chromium_tag_from_brave_package"] == "157.0.8103.30"
    assert progress["source"]["source_state_fingerprint"]
    assert progress["source"]["git_state"]["chromium"]["head"] == chromium_sha
    assert "pack_file_count" in progress["source"]["git_state"]["chromium"]

    # A later 30-minute slice that did not receive any new Git objects, complete
    # a phase, or change critical source/config files must reuse the parent shard
    # set instead of rebuilding and uploading the same archive.
    previous_manifest = module.sha256_file(root / module.MANIFEST_NAME)
    (work / ".sandium" / "source-prep-progress.txt").write_text(
        "STAGE=2\nPHASE=pinning-incomplete\nREFRESH_REQUEST_ID=unit-test\n", encoding="utf-8")
    module.archive(root, workers=2, stage=2, ready=False, skip_if_unchanged=True)
    assert (work / ".sandium" / "source-archive-unchanged").is_file()
    assert module.sha256_file(root / module.MANIFEST_NAME) == previous_manifest
    unchanged = module.load_manifest(root)[0]
    assert unchanged["stage"] == 1

    # A real source change advances the fingerprint and creates a new cumulative
    # archive that the next stage can restore.
    (src / "README.md").write_text("chromium source advanced\n", encoding="utf-8")
    run(["git", "-C", str(src), "add", "README.md"])
    run(["git", "-C", str(src), "commit", "-m", "test chromium source update"])
    chromium_sha = run(["git", "-C", str(src), "rev-parse", "HEAD"])
    (work / ".sandium" / "source-prep-progress.txt").write_text(
        "STAGE=3\nPHASE=pinning-incomplete\nREFRESH_REQUEST_ID=unit-test\n", encoding="utf-8")
    module.archive(root, workers=2, stage=3, ready=False, skip_if_unchanged=True)
    assert not (work / ".sandium" / "source-archive-unchanged").exists()
    advanced = module.verify(root, workers=2, zstd_test=False, require_ready=False)
    assert advanced["stage"] == 3
    assert advanced["source"]["actual_chromium_sha"] == chromium_sha

    # Complete the source pin and prove that the same archive format promotes
    # the exact source-ready state, while still excluding compiled objects.
    (work / ".sandium" / "source-pins.env").write_text(
        "BRAVE_CORE_TAG=v1.99.54\nBRAVE_CORE_SHA=%s\nCHROMIUM_TAG=157.0.8103.30\nCHROMIUM_SHA=%s\nREFRESH_REQUEST_ID=unit-test\n"
        % (brave_sha, chromium_sha),
        encoding="utf-8")
    (work / ".sandium" / "source-prep-progress.txt").write_text(
        "STAGE=4\nPHASE=source-ready\nREFRESH_REQUEST_ID=unit-test\n", encoding="utf-8")
    module.archive(root, workers=2, stage=2, ready=True)
    payload = module.verify(root, workers=2, zstd_test=True, require_ready=True)
    assert payload["ready"] is True
    assert payload["source"]["chromium_sha"] == chromium_sha
    assert payload["source"]["refresh_request_id"] == "unit-test"

    backup = root / "saved-original-workspace"
    os.replace(work, backup)
    module.restore(root, workers=2, require_ready=True)
    restored = root / "brave-work"
    assert (restored / ".gclient").is_file()
    assert (restored / ".gclient_entries").is_file()
    assert (restored / "src" / "brave" / "node_modules" / ".modules.yaml").is_file()
    assert (restored / "src" / "out" / "android_Release_arm64" / "build.ninja").is_file()
    assert (restored / "src" / "out" / "android_Release_arm64" / "args_generated.gni").is_file()
    assert not (restored / "src" / "out" / "android_Release_arm64" / "obj" / "example.o").exists()
    assert not (restored / "src" / "out" / "android_Release_arm64" / ".siso_fs_state").exists()
    assert run(["git", "-C", str(restored / "src" / "brave"), "describe", "--tags", "--exact-match"]) == "v1.99.54"

print("SANDIUM_SOURCE_CHECKPOINT_TEST=PASS source+dependencies+GN graph restored; compiled objects/Siso state excluded")
