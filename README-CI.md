# SanB Android Desktop validation lane

SanB is independent of the existing browser release lanes. Use the enrolled
CircleCI project only as the place to submit the isolated branch
`sanb/official158`. The config **and** checkout source must both be that
branch. The default push/tag event runs no workflow. Manual parameters:

| Goal | Parameters | Deliverable |
|---|---|---|
| Build-worker capacity audit | `run_sanb: true`, `sanb_mode: capacity-audit` | Measured mount, CPU and memory only; no source sync or APK |
| Public exact source audit | `run_sanb: true`, `sanb_mode: source-audit` | Pinned preimage evidence and strict chronological replay only; no APK |
| Worker and exact source plan | `run_sanb: true`, `sanb_mode: preflight` | Static plan and worker resource report; no APK |
| Actual Android build | `run_sanb: true`, `sanb_mode: build` | Exact generated APK if successful, otherwise the first failing phase and logs |

The `SanB` graph selects exactly one of three machine jobs. Neither has a
protected context, workspace persistence, restore/cache key, external
compiler service, signing secret or fallback build. Only the checked
source-audit job can emit a compact public, hash-addressed diagnostic
preimage archive, not a compiled checkpoint. It admits only the accepted exact Bare
release commit and an independently ported Chromium
`158.0.8127.42` Android Desktop branch. It does **not** silently fall back to
Bare's original M157. Its source adapter must first pass the exact source/
licensing review and provide a deterministic proof with no bundled uBlock
asset. The verified preparation must emit the same proof as static
admission and yield a pristine, pinned Chromium git revision with the
reviewed source changes applied in the disposable SanB work directory.

Private build contract:

```text
python3 -u tools/sanb_source.py verify --receipt PATH
python3 -u tools/sanb_source.py prepare --workspace NEW_PATH --receipt PATH
# NEW_PATH/src and NEW_PATH/depot_tools after exact pin/dependency preparation
```

Adapter receipt fields: `schema=1`, `bare` (full commit), `chromium` (full
revision), `version="158.0.8127.42"`, `android_desktop=true`,
`embedded_ublock=false`, and `patch_sha256` (lowercase 64-hex). The no-uBlock
guard also checks the known Bare CRX location, APK target graph and APK ZIP
member names. Remaining source content checks belong to the exact source
preflight, not to a name-grep substitute.

The build uses independently pinned M158's Android SDK Build Tools 37 from
Chromium's prepared source. The distinct Android package is
`io.github.sandeepbimt.sanb`, label `SanB`. The graph for the one public APK must
show no keystore, signing args or `.idsig`. The completed ZIP must contain
only ARM64 native libraries (including `libchrome.so`), no v1/v2/v3/v4
signatures, pass 16 KiB alignment and have exactly the intended non-debug
Android package and label. This artifact is **unsigned and not installable**;
a separately approved SanB signer is required for a phone test. Neither
build nor validation touches a private key.

## Source-audit mode

This mode does not run the ARM64 job, fetch DEPS/toolchains, generate GN,
compile, sign or run any upstream script. The medium worker validates the
exact annotated Bare v2.0.7 tag, commit and tree plus all 346 patch hashes;
it materializes only those patch files. For both pinned Chromium M158 and
the upstream M157 provenance base it retrieves shallow Git metadata and
only the 976 exact wanted first-preimage blob IDs. It never materializes
a Chromium worktree. The server must advertise partial clone filtering;
a declined filtered request is not permission to clone the whole tree.
The release source admission gate remains separate.

The sealed chronology runner is offline and uses only disposable indexes.
It distinguishes actual context conflicts from unread preimages, held
same-owner predecessors and policy exclusions. Results are analysis only,
even when the audit succeeds. An unread preimage set returns 3 and retains
the bounded diagnostic evidence. Service-side Git pack/filter support and
the actual live runtime are not proven by the local tests.

The audit has a shared 21-minute wall budget and a second 23-minute CI
wrapper, with no checkpoints. Audit artifacts are `status.json`,
`first-preimages.json`, `bulk-context.json`, and when within caps,
`sanb-pinned-preimages.tar.gz`. The latter contains only public Chromium
`blobs/<git-sha1>` regular object bytes (no source paths, Git metadata,
bundled CRX, or donor repository), cross-validated against the request
set. Transfer stays below a 64 MiB total / 56 MiB compressed archive cap;
an over-limit archive is omitted rather than uploaded. First-preimage
downloads and reports never describe a port as ready to build.

## Capacity-audit mode

The same Linux VM image, `large` resource class and default project directory
as Android Build/Preflight. Uses only the trusted project checkout and one
90-second-bounded measurement; it never fetches Chromium, Bare or deps.
The measured numerator is user-available disk bytes, not nominal disk size
or raw reserved space. Reports both statvfs and `df`, capacity/available
inodes, CPU/affinity/cgroup quota and host/cgroup RAM. Only the exact mount
and public runtime counters are written to `sanb-capacity-audit/status.json`
and `df.txt`. A successful measurement below the threshold yields
`measured=true, eligible_for_130_gib=false`; a measurement failure yields
`measured=false, eligible_for_130_gib=null` and fails the job. Both results
are distinct from source admission and from earning an APK, and an initial
pass does not prove usable capacity after acquisition, GN or linking.

## Bounded cold-build decision

No Cold Bare M158 build or device has been proved here. Runner preflight
requires at least 130 GiB free and reports the actual CPU/storage. Chromium
source sync, PGO profile fetches, GN and native Android compilation share
a 55-minute worker deadline with a 150-second reserve for output
verification and artifact publication. The process group is terminated at
budget; a build with less than 10 minutes remaining before Android
compilation does not launch it. No partial executable or archive is
published as an APK.

This is not a credible assumption of a one-hour cold compile: the recent
warm RawS build used an already compiled 25+ GiB reference and remote
background compile execution. A Chromium incremental restore is **not**
cold-build timing evidence. If the scoped worker cannot get through native
compile, preserve the exact source recipe and phase timings, then choose
between (1) a separately authorized independent SanB long-lived Linux
builder/remote execution namespace, at least 130 GiB usable storage,
or (2) a validated SanB-only resumable job chain that packs exactly
`out/SanB-arm64` after a measured useful slice and proves its upload/restore
fits the free runner's cap. Neither should be represented as available or
approved until its resources are verified. Do not read or copy the existing
RawS cache credentials or checkpoint even if that is faster.

## Validation and rollback

Run from this folder:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/sanb -v
```

The pinned packager test can additionally point `SANB_PINNED_PUBLIC_FIXTURE`
to a directory of the four exact upstream M158 inputs, not build outputs.
The test verifies both GN edits and fails on a modified input. Local
tests cover the config guard, release contract, API receipt, asset/signature/
ABI rejection, and two-phase source admission; they are not a native
GN, CircleCI runner or APK result. The config is standalone; do not replace
the existing RawS branch configuration with it. Roll back by not triggering
`SanB`; this does not affect other browser branches or caches.
