#!/usr/bin/env python3
"""Round-trip and integrity regression tests for parallel Sandium checkpoints."""
from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

HELPER = Path(__file__).with_name("sandium-checkpoint-shards.py")
SPEC = importlib.util.spec_from_file_location("sandium_checkpoint_shards", HELPER)
assert SPEC and SPEC.loader
SHARD_MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SHARD_MODULE)

def run(*args: str, env: dict[str, str] | None = None) -> str:
    proc = subprocess.run([sys.executable, str(HELPER), *args], env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if proc.returncode:
        raise AssertionError("command failed (%s):\n%s" % (args, proc.stdout))
    return proc.stdout


def test_idle_build_server_shutdown(root: Path) -> None:
    work = root / "idle-server-fixture" / "brave-work"
    script = work / "src" / "build" / "android" / "fast_local_dev_server.py"
    script.parent.mkdir(parents=True)
    log = work / "src" / "out" / "android_Release_arm64" / "buildserver.log.2"
    log.parent.mkdir(parents=True)
    script.write_text(
        "import sys, time\n"
        "stream = open(sys.argv[-1], 'a', encoding='utf-8')\n"
        "stream.write('ready'); stream.flush()\n"
        "time.sleep(60)\n",
        encoding="utf-8",
    )
    process = subprocess.Popen(
        [sys.executable, str(script), "--exit-on-idle", "--quiet", str(log)]
    )
    try:
        for _ in range(40):
            if log.exists() and log.stat().st_size:
                break
            if process.poll() is not None:
                raise AssertionError("idle server fixture exited before test")
            time.sleep(0.05)
        assert log.exists() and log.stat().st_size, "fixture server did not open its log"
        writers = SHARD_MODULE.find_open_writers(work)
        assert any(item["pid"] == str(process.pid) for item in writers), writers

        SHARD_MODULE.stop_idle_build_servers(work, timeout=5.0)
        process.wait(timeout=2.0)
        assert process.returncode is not None
        assert not SHARD_MODULE.find_open_writers(work)
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=2.0)


def test_hardlink_snapshot(root: Path) -> None:
    work = root / "snapshot-fixture" / "brave-work"
    source_dir = work / "src" / "out" / "android_Release_arm64" / "obj" / "base"
    source_dir.mkdir(parents=True)
    source_file = source_dir / "stable-output.bin"
    source_file.write_bytes(b"original compiled output")
    staging_file = source_dir / "temporary.stamp.staging"
    staging_file.write_bytes(b"partial temporary output")

    with source_file.open("ab") as writer:
        writers = SHARD_MODULE.find_open_writers(work)
        assert any(
            item["pid"] == str(os.getpid()) and item["path"] == str(source_file)
            for item in writers
        ), writers

    snapshot_parent = root / "snapshot-fixture" / "snapshot"
    snapshot_work = snapshot_parent / "brave-work"
    result = SHARD_MODULE.create_hardlink_snapshot(work, snapshot_work)
    snapshot_file = snapshot_work / source_file.relative_to(work)
    snapshot_dir = snapshot_file.parent
    snapshot_dir_mtime = snapshot_dir.stat().st_mtime_ns

    assert result["method"] == "same-filesystem-hardlink-directory-snapshot", result
    assert result["inventory_stable"] is True, result
    assert result["hardlinked_files"] == 1, result
    assert result["excluded_staging_files"] == 1, result
    assert source_file.stat().st_ino == snapshot_file.stat().st_ino
    assert not (snapshot_dir / staging_file.name).exists()

    # Atomic replacement/removal in the live workspace must not change the
    # namespace or contents already captured by the hard-link snapshot.
    replacement = source_dir / "stable-output.bin.new"
    replacement.write_bytes(b"new live output")
    os.replace(replacement, source_file)
    (source_dir / "created-after-snapshot.bin").write_bytes(b"late output")
    (source_dir / "removed-after-snapshot.bin").write_bytes(b"late output")
    (source_dir / "removed-after-snapshot.bin").unlink()

    assert snapshot_file.read_bytes() == b"original compiled output"
    assert snapshot_file.stat().st_ino != source_file.stat().st_ino
    assert not (snapshot_dir / "created-after-snapshot.bin").exists()
    assert not (snapshot_dir / "removed-after-snapshot.bin").exists()
    assert snapshot_dir.stat().st_mtime_ns == snapshot_dir_mtime
    shutil.rmtree(snapshot_parent, ignore_errors=True)


def main() -> None:
    if not shutil.which("zstd") or not shutil.which("tar"):
        raise SystemExit("SANDIUM_SHARD_TEST=FAIL zstd/tar unavailable")
    with tempfile.TemporaryDirectory(prefix="sandium-parallel-checkpoint-") as temporary:
        root = Path(temporary)
        work = root / "brave-work"
        src = work / "src"
        output = src / "out" / "android_Release_arm64"
        (work / ".sandium").mkdir(parents=True)
        (src / ".git").mkdir(parents=True)
        (src / "brave" / ".git").mkdir(parents=True)
        (src / "build").mkdir()
        (src / "buildtools").mkdir()
        (src / "third_party").mkdir()
        output.mkdir(parents=True)
        (work / ".gclient").write_text("solutions = []\n", encoding="utf-8")
        (src / ".git" / "HEAD").write_text("ref: refs/heads/test\n", encoding="utf-8")
        (src / "brave" / ".git" / "HEAD").write_text("ref: refs/tags/v1.98.62\n", encoding="utf-8")
        (src / "build" / "build-config.txt").write_text("build-config\n", encoding="utf-8")
        wrapper = src / "buildtools" / "python-wrapper"
        wrapper.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        os.chmod(wrapper, 0o755)
        (output / "build.ninja").write_text("ninja_required_version = 1.10\n", encoding="utf-8")
        (output / "args.gn").write_text('target_os = "android"\n', encoding="utf-8")
        (output / "args_generated.gni").write_text("use_siso=true\n", encoding="utf-8")
        (output / ".siso_fs_state.journal").write_text("journal-state\n", encoding="utf-8")
        checkpoint_lines = [
            "CHECKPOINT_VALID=true", "REFERENCE_MODE=reference",
            "APK_VALIDATED=true", "REFERENCE_READY=true",
            "REFERENCE_SOURCE_REVISION=test-revision", "BRAVE_CORE_TAG=v1.98.62",
            "CHROMIUM_SHA=d331de35ca8ab1358c7a17e4bd41627d55eaef51",
            "TARGET=android-arm64", "BUILD_TYPE=Release",
        ]
        (work / ".sandium" / "checkpoint-manifest.txt").write_text(
            "\n".join(checkpoint_lines) + "\n", encoding="utf-8")

        expected = {}
        for group in range(12):
            directory = output / "obj" / ("component-%02d" % group)
            directory.mkdir(parents=True)
            for item in range(4):
                path = directory / ("object-%02d.bin" % item)
                payload = (("component=%d object=%d " % (group, item)) * 500).encode()
                path.write_bytes(payload)
                expected[path.relative_to(root).as_posix()] = payload
        for group in range(12):
            directory = src / "third_party" / ("library-%02d" % group)
            directory.mkdir(parents=True)
            path = directory / "manifest.txt"
            payload = ("library %d\n" % group).encode()
            path.write_bytes(payload)
            expected[path.relative_to(root).as_posix()] = payload

        empty_dir = src / "third_party" / "empty-directory"
        empty_dir.mkdir()
        link = src / "third_party" / "empty-link"
        link.symlink_to("empty-directory")
        timed_file = output / "obj" / "component-00" / "object-00.bin"
        os.utime(timed_file, ns=(1700000000123456789, 1700000000123456789))
        source_mtime = timed_file.stat().st_mtime_ns
        source_mode = wrapper.stat().st_mode & 0o777

        # Prove that the hard-link namespace snapshot is isolated from later
        # creates/removals/replacements in the live build workspace.
        test_idle_build_server_shutdown(root)
        test_hardlink_snapshot(root)
        staging_file = output / "obj" / "component-00" / "temporary.stamp.staging"
        staging_file.write_text("not a final build output\n", encoding="utf-8")

        # Inject one transient GNU-tar exit status 1 after a complete tar stream.
        # The shard helper must discard that attempt and rebuild the affected shard.
        real_tar = shutil.which("tar")
        real_zstd = shutil.which("zstd")
        assert real_tar and real_zstd
        # Record compression arguments while forwarding to the real zstd binary.
        fake_bin = root / "fake-bin"
        fake_bin.mkdir()
        fake_zstd = fake_bin / "zstd"
        fake_zstd.write_text(
            "#!/usr/bin/env bash\n"
            "printf '%s\n' \"$*\" >> \"$SANDIUM_ZSTD_ARGS_LOG\"\n"
            "exec \"$SANDIUM_REAL_ZSTD\" \"$@\"\n",
            encoding="utf-8",
        )
        os.chmod(fake_zstd, 0o755)
        fake_tar = fake_bin / "tar"
        fake_tar.write_text(
            "#!/usr/bin/env bash\n"
            "set +e\n"
            "\"$SANDIUM_REAL_TAR\" \"$@\"\n"
            "status=$?\n"
            "if [ \"$status\" -eq 0 ] && mkdir \"$SANDIUM_TAR_FAIL_ONCE_LOCK\" 2>/dev/null; then\n"
            "  printf '%s\n' SANDIUM_TEST_INJECTED_TAR_EXIT_1 > \"$SANDIUM_TAR_FAIL_ONCE_LOG\"\n"
            "  exit 1\n"
            "fi\n"
            "exit \"$status\"\n",
            encoding="utf-8",
        )
        os.chmod(fake_tar, 0o755)
        test_env = os.environ.copy()
        test_env["PATH"] = str(fake_bin) + os.pathsep + test_env["PATH"]
        test_env["SANDIUM_REAL_TAR"] = real_tar
        test_env["SANDIUM_REAL_ZSTD"] = real_zstd
        test_env["SANDIUM_ZSTD_ARGS_LOG"] = str(root / "zstd-args.log")
        test_env["SANDIUM_TAR_FAIL_ONCE_LOCK"] = str(root / "tar-fail-once.lock")
        test_env["SANDIUM_TAR_FAIL_ONCE_LOG"] = str(root / "tar-fail-once.log")
        archive_output = run("archive", "--root", str(root), "--workers", "8", env=test_env)
        assert "SANDIUM_SHARD_ARCHIVE_RETRY=START" in archive_output, archive_output
        assert (root / "tar-fail-once.log").read_text(encoding="utf-8").strip() == "SANDIUM_TEST_INJECTED_TAR_EXIT_1"
        zstd_args = (root / "zstd-args.log").read_text(encoding="utf-8").splitlines()
        assert zstd_args and all("--fast=5" in args for args in zstd_args), zstd_args
        manifest_path = root / "brave-workspace-checkpoint.manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        shards = manifest["shards"]
        assert 4 <= manifest["workers"] <= 8, manifest
        assert len(shards) == manifest["workers"], manifest
        assert all(int(shard["size_bytes"]) > 0 for shard in shards), manifest
        assert all(int(shard["archive_attempts"]) in (1, 2) for shard in shards), manifest
        assert manifest["excluded_transient_patterns"] == ["*.staging"], manifest
        assert manifest["accepted_transient_read_race_count"] == 0, manifest
        assert manifest["source_snapshot"]["method"] == "same-filesystem-hardlink-directory-snapshot", manifest
        assert manifest["source_snapshot"]["inventory_stable"] is True, manifest
        assert manifest["source_snapshot"]["hardlinked_files"] > 0, manifest
        assert manifest["source_snapshot"]["excluded_staging_files"] == 1, manifest
        assert any(int(shard["archive_attempts"]) == 2 for shard in shards), manifest
        assert len({shard["sha256"] for shard in shards}) == len(shards), manifest
        verified = run("verify", "--root", str(root), "--workers", "8", "--zstd-test")
        assert "SANDIUM_SHARD_VERIFY=PASS" in verified, verified

        shutil.rmtree(work)
        restored = run("restore", "--root", str(root), "--workers", "8")
        assert "SANDIUM_PARALLEL_RESTORE=PASS" in restored, restored
        for relative, payload in expected.items():
            assert (root / relative).read_bytes() == payload, "payload mismatch: " + relative
        assert not staging_file.exists(), "Ninja .staging file must not enter checkpoint archive"
        assert (src / "third_party" / "empty-directory").is_dir()
        assert link.is_symlink() and os.readlink(link) == "empty-directory"
        assert (wrapper.stat().st_mode & 0o777) == source_mode
        assert timed_file.stat().st_mtime_ns == source_mtime
        for required in (work / ".gclient", output / "build.ninja",
                        output / "args.gn", output / ".siso_fs_state.journal",
                        work / ".sandium" / "checkpoint-manifest.txt"):
            assert required.is_file(), str(required)

        shard_path = root / "brave-workspace-checkpoint.shards" / shards[0]["name"]
        # Flip one byte without changing length so verification proves the
        # SHA-256 check, rather than merely detecting a truncated/extended file.
        with shard_path.open("r+b") as stream:
            first = stream.read(1)
            assert first, "empty shard"
            stream.seek(0)
            stream.write(bytes([first[0] ^ 0x01]))
        bad = subprocess.run([sys.executable, str(HELPER), "verify", "--root", str(root),
                              "--workers", "8"], stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True)
        assert bad.returncode != 0 and "SHA256 mismatch" in bad.stdout, bad.stdout
    print("SANDIUM_PARALLEL_CHECKPOINT_TEST=PASS 8-way hard-link snapshot/archive/verify/restore; live-workspace isolation; staging exclusion; symlink/mode/mtime preservation; tar retry; tamper detection")

if __name__ == "__main__":
    main()
