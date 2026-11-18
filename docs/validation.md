# Baseline gates and current limits

## Local checks
Run unittest and py_compile. These validate scaffold/safety behavior only, not
Chromium compilation. Empty feature/patch manifests are intentional.

## Full build host
Official Chromium guidance calls for Linux, >=100GB disk and >=8GB RAM (>16GB
recommended). This executor has about56GiB free: preflight correctly refuses a
full checkout. Initial direct upstream shell connection timed out; a permitted network retry
verified the official depot_tools revision. Disk remains the full-build blocker,
not a source compilation failure. No APK has been built by this project.

## CI
The .circleci/config.yml is opt-in (run_raw_preflight=false by default) and guards the raw-sandium/bootstrap branch. Its first job only runs scaffold tests and a120-second host/network probe, not checkout/compile of Chromium. It has no connection
to existing Sandium cache namespaces, artifacts or credential contexts. A clean
Chromium build still needs a sufficiently provisioned host; the existing25-minute
Sandium checkpoint strategy is not yet ported here. Do not enable a cold full
compile on a one-hour worker hoping it completes. First measure checkout/toolchain
and compile costs, then design isolated pinned-source build cache and stage
receipts. No published remote project or new pipeline is assumed by these files.

## Device acceptance (pending)
Install separately on ARM64 Android, identify version/package; compare stock
navigation with current Sandium, recording cold/warm URL, external intent,
Google-result link, back/forward, homepage, hidden toolbar, keyboard and cancelled
predictive Back. Repeat dark/light transitions, ad-heavy pages, settings restart,
renderer crash recovery. Capture video/log timeline together and distinguish
frame presentation from renderer events. No masking delays or overlays passed
as navigation fixes.

## First actual CI probe: pipeline1365
Checkout, branch guard and13 scaffold tests passed. Host free disk143007555584
bytes, memory16464265216 bytes,4CPUs. Official depot_tools endpoint returned200.
GitHub raw VERSION mirror returned HTTPError, so probe failed before any compile.
Next probe uses canonical Chromium Gitiles and records HTTP status explicitly.
