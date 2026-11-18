# Raw Sandium

Independent Chromium Android baseline and maintainable Sandium feature layer.
**Scaffold, not a built APK.** Existing Sandium-2 branches, pipeline and user data
are untouched. The first APK deliberately retains Chromium branding; renaming an
artifact is not rebranding the application.

## Reproducible baseline
Chromium **156.0.8078.74**, commit `d331de35ca8ab1358c7a17e4bd41627d55eaef51`.
This matches the Chromium under the existing Sandium reference so the first
comparison changes the Brave layer, not the browser engine version. It is not a
claim that this is the latest secure release. Version provenance is in the lock.
No Brave source, caches, patches or credential configuration are imported.

The `depot_tools` lock is intentionally unresolved until an upstream connection
can verify its exact revision. The build fails closed until that pin is committed.

## Commands
```sh
python3 -m unittest discover -s tests -v
python3 tools/raw.py preflight --workspace /large-disk/raw-sandium
python3 tools/raw.py resolve-tools  # inspect and commit resolved lock
python3 tools/raw.py setup --workspace /large-disk/raw-sandium
# On that Linux host, install upstream OS packages (requires system authorization):
# /large-disk/raw-sandium/src/build/install-build-deps.sh
python3 tools/raw.py build --workspace /large-disk/raw-sandium
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
