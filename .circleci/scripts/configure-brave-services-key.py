#!/usr/bin/env python3
"""Inject a CircleCI-provided Brave Services key into the ephemeral Brave .env file."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ENV_NAME = "BRAVE_SERVICES_KEY"
CONFIG_NAME = "brave_services_key"


def load_key() -> str:
    value = os.environ.get(ENV_NAME, "")
    if not value:
        raise SystemExit(
            "BRAVE_SERVICES_KEY_GATE=FAIL missing CircleCI environment variable BRAVE_SERVICES_KEY"
        )
    if value != value.strip() or any(ch.isspace() for ch in value) or "\x00" in value:
        raise SystemExit(
            "BRAVE_SERVICES_KEY_GATE=FAIL value contains whitespace or an invalid NUL character"
        )
    return value


def configure_env(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    preserved = [
        line for line in existing
        if line.partition("=")[0].strip() != CONFIG_NAME
    ]
    content = "\n".join([*preserved, f"{CONFIG_NAME}={value}"]) + "\n"

    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.sandium-", dir=str(path.parent)
    )
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as temporary:
            temporary.write(content)
        os.replace(temporary_name, path)
        os.chmod(path, 0o600)
    except BaseException:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def main() -> None:
    if len(sys.argv) == 2 and sys.argv[1] == "--validate":
        load_key()
        print("BRAVE_SERVICES_KEY_GATE=PASS source=CircleCI environment variable value=REDACTED")
        return
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: configure-brave-services-key.py --validate|<brave-core/.env path>"
        )

    configure_env(Path(sys.argv[1]), load_key())
    print("BRAVE_SERVICES_KEY_CONFIG=PASS destination=Brave .env value=REDACTED")


if __name__ == "__main__":
    main()
