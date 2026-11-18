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

## Canonical Git follow-up

The official Git protocol independently resolved tag `156.0.8078.74` to
`d331de35ca8ab1358c7a17e4bd41627d55eaef51`. This is stronger source-identity
evidence than a failing Gitiles HTTP request. It does not prove a complete
checkout or working compiler.

The opt-in `run_raw_bootstrap` job verifies that tag again on CircleCI,
fetches only pinned depot_tools and Chromium commit objects, and reads
`chrome/VERSION` through Git. It retries each network operation once and has
an 18-minute outer limit. It neither compiles nor restores any old cache.
All diagnosis is saved as a JSON artifact, including failed attempts.

Before a full compile pipeline is enabled, independent source/dependency sync,
OS dependencies and hooks must succeed. Proposed phase boundaries are:
1. Pinned source plus Android dependencies, with exact lock-keyed persistence.
2. Toolchain hooks and GN generation, with resolved toolchain receipts.
3. 25-minute compile slices on exactly that state; persist only on slice expiry.
4. APK verification and artifact publication, then skip all later stages.
Any genuine build failure terminates the chain, not another slice. No phase may
read a Brave checkpoint. Compilation remains disabled pending those validations.

## Staged build candidate (not yet compiled)

`run_raw_source` performs a fresh, shallow-history Android dependency sync with
a 25-minute bound. A successful exact source identity check is required before
handing that workflow's tree to later jobs. #1372 is the first actual source-sync
trial. It is separate from the successful smaller #1371 provenance bootstrap.

The `run_raw_full` opt-in candidate chains that source job with three sequential
25-minute compiler slices. These are not a claim of a validated build. Each
worker installs official OS dependencies and runs pinned toolchain hooks first.
Only compiler time-slice expiry permits an output checkpoint; compilation
errors fail the chain. Output archives are workflow-local, checksum verified,
and never use the Brave pipeline's state. Earlier APK completion is cached as a
tiny optimization marker so subsequent jobs can skip before downloading source;
a cache miss remains safe because the workspace contains authoritative state.
Each slice has unique handoff paths, avoiding concurrent workspace collisions.
If three slices expire, the last job reports incomplete rather than success.

Known tradeoffs pending real measurements: source workspace transfer is large;
toolchain hooks and OS packages are repeated on workers; checkpoint archives
need spare disk. Guards fail safely rather than claiming resumability if disk
is insufficient. Do not enable more slices or broader caching without measuring.
