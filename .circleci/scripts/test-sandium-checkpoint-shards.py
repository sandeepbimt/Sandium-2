#!/usr/bin/env python3
"""Round-trip and integrity regression tests for parallel Sandium checkpoints."""
from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HELPER = Path(__file__).with_name("sandium-checkpoint-shards.py")

def run(*args: str, env: dict[str, str] | None = None) -> str:
    proc = subprocess.run([sys.executable, str(HELPER), *args], env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if proc.returncode:
        raise AssertionError("command failed (%s):\n%s" % (args, proc.stdout))
    return proc.stdout

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
        (work / ".sandium" / "action-ledger.json").write_text(
            json.dumps({"schema_version": 2, "planned_total": 2, "completed": {},
                        "next_pending_action_keys": ["a", "b"]}), encoding="utf-8")
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
            "#!/usr/bin/env bash\\n"
            "printf '%s\\n' \"$*\" >> \"$SANDIUM_ZSTD_ARGS_LOG\"\\n"
            "exec \"$SANDIUM_REAL_ZSTD\" \"$@\"\\n",
            encoding="utf-8",
        )
        os.chmod(fake_zstd, 0o755)
        fake_bin = root / "fake-bin"
        fake_bin.mkdir()
        fake_tar = fake_bin / "tar"
        fake_tar.write_text(
            "#!/usr/bin/env bash\n"
            "set +e\n"
            "\"$SANDIUM_REAL_TAR\" \"$@\"\n"
            "status=$?\n"
            "if [ \"$status\" -eq 0 ] && mkdir \"$SANDIUM_TAR_FAIL_ONCE_LOCK\" 2>/dev/null; then\n"
            "  echo SANDIUM_TEST_INJECTED_TAR_EXIT_1 >&2\n"
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
        archive_output = run("archive", "--root", str(root), "--workers", "8", env=test_env)
        assert "SANDIUM_SHARD_ARCHIVE_RETRY=START" in archive_output, archive_output
        assert "SANDIUM_TEST_INJECTED_TAR_EXIT_1" in archive_output, archive_output
        zstd_args = (root / "zstd-args.log").read_text(encoding="utf-8").splitlines()
        assert zstd_args and all("--fast=5" in args for args in zstd_args), zstd_args
        manifest_path = root / "brave-workspace-checkpoint.manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        shards = manifest["shards"]
        assert 4 <= manifest["workers"] <= 8, manifest
        assert len(shards) == manifest["workers"], manifest
        assert all(int(shard["size_bytes"]) > 0 for shard in shards), manifest
        assert all(int(shard["archive_attempts"]) in (1, 2) for shard in shards), manifest
        assert any(int(shard["archive_attempts"]) == 2 for shard in shards), manifest
        assert len({shard["sha256"] for shard in shards}) == len(shards), manifest
        verified = run("verify", "--root", str(root), "--workers", "8", "--zstd-test")
        assert "SANDIUM_SHARD_VERIFY=PASS" in verified, verified

        shutil.rmtree(work)
        restored = run("restore", "--root", str(root), "--workers", "8")
        assert "SANDIUM_PARALLEL_RESTORE=PASS" in restored, restored
        for relative, payload in expected.items():
            assert (root / relative).read_bytes() == payload, "payload mismatch: " + relative
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
    print("SANDIUM_PARALLEL_CHECKPOINT_TEST=PASS 8-way archive/verify/restore; symlink/mode/mtime preservation; tamper detection")

if __name__ == "__main__":
    main()
