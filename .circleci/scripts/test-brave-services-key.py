#!/usr/bin/env python3
"""Exercise Brave Services key validation and safe .env injection."""
from __future__ import annotations

import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

HELPER = Path(__file__).with_name("configure-brave-services-key.py")


def run(args: list[str], key: str | None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if key is None:
        env.pop("BRAVE_SERVICES_KEY", None)
    else:
        env["BRAVE_SERVICES_KEY"] = key
    return subprocess.run(
        [sys.executable, str(HELPER), *args],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def main() -> None:
    fake = "test-only-SANDIUM-service-key-DO-NOT-USE"
    with tempfile.TemporaryDirectory(prefix="sandium-service-key-test-") as directory:
        env_file = Path(directory) / ".env"
        env_file.write_text(
            "rbe_service=remote.buildbuddy.io:443\n"
            "use_remoteexec=true\n"
            "brave_services_key=stale-value\n"
            "other_setting=preserved\n",
            encoding="utf-8",
        )

        good = run([str(env_file)], fake)
        if good.returncode:
            raise SystemExit(
                f"BRAVE_SERVICES_KEY_TEST=FAIL valid test key rejected: {good.stderr.strip()}"
            )
        lines = env_file.read_text(encoding="utf-8").splitlines()
        actual = [line for line in lines if line.startswith("brave_services_key=")]
        if actual != [f"brave_services_key={fake}"]:
            raise SystemExit("BRAVE_SERVICES_KEY_TEST=FAIL key not replaced exactly once")
        if "rbe_service=remote.buildbuddy.io:443" not in lines or "other_setting=preserved" not in lines:
            raise SystemExit("BRAVE_SERVICES_KEY_TEST=FAIL unrelated .env settings not preserved")
        if stat.S_IMODE(env_file.stat().st_mode) != 0o600:
            raise SystemExit("BRAVE_SERVICES_KEY_TEST=FAIL .env mode is not 0600")
        if fake in good.stdout + good.stderr:
            raise SystemExit("BRAVE_SERVICES_KEY_TEST=FAIL helper printed key")

        original = env_file.read_text(encoding="utf-8")
        missing = run([str(env_file)], None)
        if missing.returncode == 0 or env_file.read_text(encoding="utf-8") != original:
            raise SystemExit("BRAVE_SERVICES_KEY_TEST=FAIL missing key modified .env")

        invalid = run([str(env_file)], "bad\nmultiline")
        if invalid.returncode == 0 or env_file.read_text(encoding="utf-8") != original:
            raise SystemExit("BRAVE_SERVICES_KEY_TEST=FAIL multiline key modified .env")
        if fake in missing.stdout + missing.stderr + invalid.stdout + invalid.stderr:
            raise SystemExit("BRAVE_SERVICES_KEY_TEST=FAIL failure output disclosed prior key")

        validated = run(["--validate"], fake)
        if validated.returncode or fake in validated.stdout + validated.stderr:
            raise SystemExit("BRAVE_SERVICES_KEY_TEST=FAIL validation failed or printed key")

    print(
        "BRAVE_SERVICES_KEY_TEST=PASS replacement, preservation, validation, permissions, and redaction"
    )


if __name__ == "__main__":
    main()
