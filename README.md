# Raw Sandium

Independent Chromium Android baseline and maintainable Sandium feature layer.
This branch prepares Chromium **158.0.8127.42** in official build mode for the
established RawS Full pipeline. The candidate APK is pending CI verification.
Existing Sandium branches, pipeline and user data remain separate.

## Reproducible candidate
Chromium commit `52bdd21723d5db0c9ab11716d38feac74828cf84` was verified against
ChromiumDash Android Stable and exact official `chrome/VERSION` on 2026-11-18.
See [upgrade evidence and safeguards](docs/official158-upgrade.md).
The verified Chromium 156 baseline and #1390 final archive remain on
`raw-sandium/bootstrap`; they are not compatible output inputs for this candidate.
No Brave source, caches or product patches are imported. The proven Full
CI/checkpoint engine uses a revision/configuration-specific RawS namespace and
the existing authorized BuildBuddy project credential without copying its value.

The `depot_tools` revision is independently verified against the official remote
and pinned in the lock. Automatic tool updates are disabled.

## Commands
```sh
python3 -m unittest discover -s tests -v
python3 tools/raw.py preflight --workspace /large-disk/raw-sandium
python3 tools/raw.py setup --workspace /large-disk/raw-sandium
# On that Linux host, install upstream OS packages (requires system authorization):
# /large-disk/raw-sandium/src/build/install-build-deps.sh
# Compile through the opt-in RawS full workflow (strict remote, verified checkpoints).
```
Use an empty dedicated workspace. The script refuses existing unowned directories
and the project itself. Source is pinned and verified; dependency versions follow
Chromium DEPS. Tool auto-update is disabled. A successful build emits the APK and
hash/provenance receipt to `artifacts/`; it does not install or publish the APK.

## What this does not claim
No Sandium features or uBO are ported yet. No device performance or navigation
quality is verified. Chromium phone extension support, MV2 compatibility and
Shields parity remain separate engineering work, not a GN switch promise.
The baseline app may share Chromium's package identifier with an existing
Chromium installation: do not install over another browser. Product package,
signing, profile migration and trademark choices precede any release.

See [architecture](docs/architecture.md) and [validation](docs/validation.md).

See [Full lifecycle and Chromium upgrades](docs/full-upgrades.md).
