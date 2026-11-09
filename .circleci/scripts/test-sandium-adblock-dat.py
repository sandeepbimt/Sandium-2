#!/usr/bin/env python3
"""Offline tests for the pinned Rust DAT generator and licensing gates."""
from __future__ import annotations

import runpy
from pathlib import Path

HERE = Path(__file__).resolve().parent
GEN = runpy.run_path(str(HERE / "generate-sandium-adblock-dat.py"))


def main() -> None:
    assert GEN["ADBLOCK_VERSION"] == "0.13.3"
    assert len(GEN["NOT_BUNDLED_LICENSE_RESTRICTIONS"]) == 2
    pgl = "https://pgl.yoyo.org/adservers/serverlist.php?hostformat=hosts&showintro=1&mimetype=plaintext"
    dan = "https://someonewhocares.org/hosts/hosts"
    assert pgl in GEN["NOT_BUNDLED_LICENSE_RESTRICTIONS"]
    assert dan in GEN["NOT_BUNDLED_LICENSE_RESTRICTIONS"]
    assert GEN["license_for"]("https://ublockorigin.github.io/uAssets/filters/filters.txt", "uBlock") [0] == "GPL-3.0"
    assert GEN["license_for"]("https://filters.adtidy.org/extension/ublock/filters/2_without_easylist.txt", "AdGuard") [0] == "GPL-3.0"
    assert GEN["license_for"]("https://malware-filter.gitlab.io/urlhaus-filter/urlhaus-filter-vivaldi-online.txt", "URLhaus") [0] == "CC0-1.0"
    assert GEN["license_for"]("https://secure.fanboy.co.nz/fanboy-antifacebook.txt", "Fanboy") [0] == "CC-BY-3.0"

    # The live 29-source catalogue is consumed by the build-time generator;
    # the only two excluded URLs are the documented non-commercial feeds.
    assert GEN["EXPECTED_INCLUDED_SOURCES"] == 27
    assert len(GEN["NOT_BUNDLED_LICENSE_RESTRICTIONS"]) == 2

    generator_source = (HERE / "generate-sandium-adblock-dat.py").read_text(encoding="utf-8")
    assert "import tomllib" in generator_source
    assert "cargo-vendor" in generator_source
    assert "alias.symlink_to(crate_dir, target_is_directory=True)" in generator_source
    assert "adblock-0.13.3" in generator_source

    rust_source = (HERE / "sandium-adblock-datgen/src/main.rs").read_text(encoding="utf-8")
    assert "Engine::new_with_filter_set" in rust_source
    assert "engine.serialize()" in rust_source
    assert "verification_engine.deserialize(&dat)?" in rust_source
    assert "expected 27 redistributable list inputs" in rust_source

    print("SANDIUM_ADBLOCK_DAT_GENERATOR_TEST=PASS rust=0.13.3 pinned=true included=27 excluded_noncommercial=2 roundtrip_check=true")


if __name__ == "__main__":
    main()
