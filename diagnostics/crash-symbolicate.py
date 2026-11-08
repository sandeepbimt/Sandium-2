#!/usr/bin/env python3
"""Symbolicate checked-in Android tombstone text using the exact restored ELF."""
import argparse
import pathlib
import re
import subprocess
import sys

EXPECTED_BUILD_ID = "bbbb704b5b2490fd1931a765ef810b2abfff2127"
FRAME_RE = re.compile(r"^\\s*#(?P<frame>\\d+)\\s+pc\\s+(?P<pc>[0-9a-fA-F]+)\\s+libchrome\\.so", re.M)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--input-dir", required=True)
    args = ap.parse_args()
    root = pathlib.Path(args.root)
    input_dir = pathlib.Path(args.input_dir)
    elf = root / "crash-symbols/libchrome.so"
    if not elf.is_file():
        raise SystemExit("SYMBOLICATION=FAIL missing exact libchrome.so")
    build = subprocess.check_output(["readelf", "-n", str(elf)], text=True)
    match = re.search(r"Build ID:\\s*([0-9a-fA-F]+)", build)
    if not match or match.group(1).lower() != EXPECTED_BUILD_ID:
        raise SystemExit("SYMBOLICATION=FAIL ELF Build ID mismatch")
    candidates = [
        root / "brave-work/src/third_party/llvm-build/Release+Asserts/bin/llvm-symbolizer",
        root / "brave-work/src/third_party/llvm-build/Release/bin/llvm-symbolizer",
        root / "depot_tools/third_party/llvm-build/Release+Asserts/bin/llvm-symbolizer",
    ]
    symbolizer = next((p for p in candidates if p.is_file()), None)
    if symbolizer is None:
        found = subprocess.run(["bash", "-lc", "command -v llvm-symbolizer"], text=True, capture_output=True)
        if found.returncode == 0 and found.stdout.strip():
            symbolizer = pathlib.Path(found.stdout.strip())
    if symbolizer is None:
        raise SystemExit("SYMBOLICATION=FAIL llvm-symbolizer not found in restored toolchain")
    inputs = sorted(input_dir.glob("tombstone_*.txt"))
    if not inputs:
        raise SystemExit("SYMBOLICATION=FAIL no tombstone_*.txt inputs found")
    out_dir = root / "crash-symbols"
    summary = []
    for src in inputs:
        raw = src.read_text(errors="replace")
        frames = list(FRAME_RE.finditer(raw))
        if not frames:
            summary.append(f"{src.name}: no libchrome.so frames found")
            continue
        pcs = [m.group("pc") for m in frames]
        cmd = [str(symbolizer), f"--obj={elf}", "--demangle", "--inlines", "--functions=linkage"]
        proc = subprocess.run(cmd, input="\\n".join(pcs) + "\\n", text=True, capture_output=True)
        if proc.returncode:
            raise SystemExit(f"SYMBOLICATION=FAIL {src.name}: {proc.stderr}")
        resolved = proc.stdout.splitlines()
        report = [
            f"INPUT={src.name}",
            f"ELF_BUILD_ID={EXPECTED_BUILD_ID}",
            f"ELF={elf}",
            f"SYMBOLIZER={symbolizer}",
            f"FRAME_COUNT={len(pcs)}",
            "NOTE=PC values are passed as tombstone-relative ELF addresses; confirm load-bias interpretation against the original mapping before treating source lines as definitive.",
            "",
        ]
        # llvm-symbolizer emits one or more lines per address. Preserve its complete output.
        for i, pc in enumerate(pcs):
            report.append(f"FRAME #{frames[i].group('frame')} pc 0x{pc}")
            report.append(resolved[i] if i < len(resolved) else "<no symbol>")
            if i + 1 < len(resolved) and resolved[i + 1].strip():
                report.append(resolved[i + 1])
            report.append("")
        dest = out_dir / f"{src.stem}.symbolicated.txt"
        dest.write_text("\\n".join(report) + "\\n")
        summary.append(f"{src.name}: {len(pcs)} libchrome frames -> {dest.name}")
    (out_dir / "symbolication-summary.txt").write_text(
        "SYMBOLICATION=PASS\\n" + "\\n".join(summary) + "\\n"
    )
    print((out_dir / "symbolication-summary.txt").read_text(), end="")

if __name__ == "__main__":
    main()
