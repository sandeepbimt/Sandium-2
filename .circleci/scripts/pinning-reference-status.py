#!/usr/bin/env python3
"""Read-only readiness gates for the shared pinned Brave/Chromium source reference."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("preflight", "result"))
    parser.add_argument("--root", required=True)
    parser.add_argument("--request-id-file", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    root = Path(args.root).resolve()
    request_id = Path(args.request_id_file).read_text(encoding="utf-8").strip()
    if not request_id:
        raise SystemExit("PINNING_STATUS=FAIL empty source refresh request ID")
    manifest_path = root / "brave-source-checkpoint.manifest.json"
    data = None
    if manifest_path.is_file():
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SystemExit("PINNING_STATUS=FAIL invalid manifest: %s" % exc)
    source = (data or {}).get("source", {})
    ready = (data or {}).get("ready") is True and source.get("refresh_request_id") == request_id
    already = ready and args.command == "preflight"
    if args.command == "result":
        preflight = root / "pinning-status" / "stage-1-preflight.env"
        if preflight.is_file():
            already = "READY_ALREADY=true" in preflight.read_text(encoding="utf-8").splitlines()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    reason = "matching-ready-reference" if ready else (
        "refresh-request-changed" if (data or {}).get("ready") else "pinning-incomplete-or-missing"
    )
    output.write_text(
        "PINNING_READY=%s\nREADY_ALREADY=%s\nREFRESH_REQUEST_ID=%s\nREASON=%s\n" % (
            "true" if ready else "false",
            "true" if already else "false",
            request_id,
            reason,
        ),
        encoding="utf-8",
    )
    print("PINNING_%s=PASS ready=%s already=%s reason=%s" % (
        args.command.upper(), ready, already, reason
    ))

if __name__ == "__main__":
    main()
