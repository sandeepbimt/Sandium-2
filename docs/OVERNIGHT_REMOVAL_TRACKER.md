# Sandium overnight Origin-feature removal tracker

Prepared from the owner's agreed 13-group scope and the published plan at Sandium commit `09d774a94289c9a339adee7a0db247d28c395b8e`. Current implementation audit reads `104df3f`, supplied by the integration coordinator as the latest baseline. Do not substitute the older #1075 browser for the latest accepted UI/filter/popup work. Coordinator must resolve the full commit SHA and current APK/run acceptance before branching.

## Exact scope and initial status

| # | Agreed group | Current evidence / remaining work |
|---|---|---|
| 1 | Email aliases | Earlier exact-pin audit showed Android excluded by derived upstream flag. Reverify generated graph and package; do not add a nonexistent GN argument. |
| 2 | Leo / AI Chat | Still retained by latest vanilla-component contract. Needs Android tabs target, observers, Java/JNI/resources, service and UI removal. |
| 3 | Brave News | Still retained. Prior isolated candidate was never deployed; reconstruct/review before use. Remove NTP feed/service, settings, Java/JNI and resources without damaging Sandium homepage. |
| 4 | Playlist | Prior code suppresses runtime allowance/factory. Android asserts enabled. Requires dependency adaptation, not deleting assertion or disabling at runtime. |
| 5 | Rewards + browser-based Brave Ads | Retained. Remove ledger/ads/promotion services, notifications and resources; Shields and blocking must remain. |
| 6 | Speedreader | Current prepare requests GN false; earlier pin audit Android default excluded. Need build/package proof. |
| 7 | Talk | Current prepare requests GN false. Need graph/package proof and removal of exclusive Android UI/hooks. Keep ordinary website WebRTC. |
| 8 | Tor | Current prepare requests GN false; earlier pin audit Android default excluded. Keep normal private browsing. |
| 9 | VPN | Retained. Audit both VPN v1/v2 declared flags; derived enable_brave_vpn is not an override. Remove app/startup/billing/manifest/WireGuard/exclusive resources. |
| 10 | Wallet + Web3 domains | Retained. Remove UI, services, provider injection, native bridges and special domain resolution. Preserve general crypto/WebCrypto/TLS and inert valuable legacy data. |
| 11 | Wayback Machine | Current prepare requests GN false; upstream Android default excluded. Need graph/package proof, not blocking visits to archive.org. |
| 12 | Web Discovery Project | Current prepare requests both general and Android-native flags false. Need absence proof for collection/upload and Android integration. |
| 13 | Reporting: daily usage ping + crash reporting + P3A | Current app still uses runtime defaults for reporting. Previous daily-updater candidate was not accepted (#1077 failed before compile). Recover/review its Java/JNI/parameter-source exclusion. P3A and remote crash uploads need separate removal. Keep local diagnostics and essential security/filter updates. |

Status vocabulary: **remaining**, **candidate only**, **not applicable/absent upstream (source proof)**, **excluded in generated graph**, **absent in APK**, **runtime/upgrade verified**. Do not collapse these into a premature “removed”. All 13 are currently short of complete release verification in this tracker.

## Current source blockers verified at 104df3f

- `prepare-brave-source.sh` still uses `MINIMAL_VANILLA_BUILD=false`, adds only Talk/Wayback/Speedreader/Tor/Web Discovery GN exclusions.
- `verify-sandium-vanilla-brave.py` restores AI/Wallet/News and Android linkage, strips their explicit GN overrides, and verifies these modules remain upstream-unmodified. This contract conflicts with actual removal. Replace it carefully with explicit product-manifest validation; do not merely delete failing tests.
- Restore pinned source once before feature overlays. Late restoration previously erased a Sandium adblock preference registration and caused a startup crash.
- No paid Origin entitlement shortcut or `is_brave_origin_branded` hack. This is source-built Sandium feature exclusion.

## Ordered implementation plan

1. **Freeze latest working baseline and isolate recipe.** Preserve latest branding/filter/popup work, exact upstream pins, signing/package identity. Create separate branch and compatible checkpoint lineage. Fingerprint effective GN arguments, removal manifest, patch order/content, toolchain and all feature-package files. Completion must match exact recipe/APK, not only name/package.
2. **Recover validated foundation, not old app.** Reuse only reviewed recipe guards and daily-updater patch from old lean work. Correct #1077 audit runner to use the established Brave GN environment and print all stdout/stderr. The old failure's exact hidden error was never recovered; missing Python path was a strong hypothesis, not proven crash output.
3. **Prove low-coupling groups.** Audit 1/6/7/8/11/12 generated dependencies and packaging, clean remaining exclusive integration if present. Group already absent on Android is not a new deletion.
4. **Daily usage updater first true native removal.** Remove exclusive updater/parameter sources and Android Java restart call, JNI declaration and native function as a unit. Preserve Safe Browsing JNI. Compile and checkpoint before wider edits.
5. **News next, isolated patch.** Prior work found settings NPE risk: removing `brave_news_v2` XML while leaving unconditional ordering dereferences null. Remove/guard both. Keep wallpaper/top-sites/local Shields stats. Feature package must precede other overlapping BraveActivity edits and be included in recipe fingerprint.
6. **Separate VPN, Leo, Rewards/Ads, Wallet and Playlist batches.** For each, inventory complete native target closure + Java/JNI/Mojo + resources/manifest + services/jobs before toggling GN arguments. Build each separately or only combine tightly related changes with explicit tests. Do not stack unvalidated high-coupling deletions merely to meet an overnight deadline.
7. **Finish reporting.** Remove remote usage/P3A/crash integrations and their consumers; retain local logs, crash handling and updater functionality needed for security/filter resources. Remote reporting and local crash diagnostics are distinct.
8. **Final acceptance.** Compare clean-output and incremental builds; inspect DEX/resources/manifest/link inputs; run fresh-install and upgrade checks. Report incomplete groups honestly if the time window ends.

## Per-group acceptance and per-run report

For each run publish: exact commit, scope/batch, 13-row status delta, APK availability, tests passed/failed/not-run, checkpoint save/restore proof, next blocker. A saved checkpoint is not a finished APK. A green compile is not a runtime proof.

Each group needs: no implementation in generated dependency closure; no exclusive APK content; no startup factory/provider/job; no runtime UI/deep-link activation; controlled network checks; old prefs/data cannot re-enable it; upgrade/startup/settings/media/downloads/passwords/tabs/Shields/filter-update tests. Shared retained code, mandatory legal notices and harmless migration identifiers are documented exceptions, not failures.

Never silently delete existing wallet or valuable user data. Never strip all strings containing “Brave” or all files containing “ads”. Sync is not one of the 13 groups. Original browser engine privacy/security functionality stays.

## Flow constraints

One Flow pipeline, not Full/Fast. Enforce one-hour job budget including restore, prepare, GN, build, shutdown, delta capture and upload. Stop compilation with checkpoint reserve. Reuse valid unchanged outputs through correct dependency checking. Keep known-good canonical payloads immutable. New recipe may import a compatible base, but must regenerate/validate its graph and must not accept an older product's APK completion marker. Verify base+delta reconstruction and deletion handling rather than only completion shortcuts. Do not combine removal with untested archive-codec changes.

## Evidence sources

- Published agreed plan: `https://github.com/sandeepbimt/Sandium-2/blob/09d774a94289c9a339adee7a0db247d28c395b8e/docs/SANDIUM_LEAN_REMOVAL_PLAN.md`
- Published first-candidate ledger: same revision, `docs/LEAN_IMPLEMENTATION_LEDGER.md`.
- Current read-only code audit: `https://github.com/sandeepbimt/Sandium-2/blob/104df3f/.circleci/scripts/verify-sandium-vanilla-brave.py` and `prepare-brave-source.sh`.

This document does not claim new implementation, push, build or device verification. It is the handoff plan for the authorized overnight work.

## Integration candidate, 13 November 2026 overnight

All thirteen groups now have source candidates integrated on the latest UI base. Native graph, Android compilation, final APK and runtime proof remain pending. Rewards retains the pinned `core:core` compatibility library (preference registration, publisher helpers, flags and policy/country support helpers); it is not the Rewards service/engine or browser Ads implementation. Its exact source list is independently gated so it cannot silently gain a service source. P3A likewise retains only documented compatibility headers and enum conversion. These are explicit shared-code exceptions, not claims of zero residual feature-related identifiers. The APK DEX audit checks actual class definitions and includes Brave's real `brave_leo` package.

DEX prefix checks alone cannot establish absence of R8-obfuscated implementation. Generated dependency/source exclusions are mandatory separate gates; final binary review must also consider mapping and retained resources. Native compile success plus original-package DEX absence is not equivalent to device/runtime verification.

## Run 1092 source-composition correction (14 November 2026)

- Commit `52eaabc` passed preflight and restored the accepted base plus three deltas. Two restore inventories completed in 16m24s; comparison with the earlier 19m15s run is observational, not a controlled benchmark.
- The combined removal phase failed before final GN generation/compilation because the earlier UI overlay added `app:isPreferenceVisible="false"` to the News settings row. The deletion transform expected only the pristine pinned row.
- Correction accepts precisely the pristine or known hidden row, still rejects unknown/ambiguous variants, and deletes the whole row. Regression composition now includes main-preference visibility, customize-menu, privacy/search preferences, main-menu icon, VPN-callout and removed-Origin ordering overlays through fresh, reset and interrupted recovery passes. This also exposed and corrected the exact existing VPN-callout guard variant, removing the entire callout block and obsolete flag rather than hiding it. Unknown News row variants remain fail-closed.
- This is source-level evidence only. No APK was generated by run 1092 and none of the thirteen groups is yet verified absent from a final artifact.

### Bounded continuation budget

The next candidate uses a shared job-start-based save policy in compilation and capture: 300 seconds only for a validated ordinary delta chain with no seven-layer rollup or expiry/base refresh due through the entire remaining one-hour horizon; otherwise 600 seconds. The 900-second capture allowance and 60-second graceful shutdown remain. An explicit 180 seconds is reserved for post-build export/audit and artifact work, within the 55-minute internal deadline and five-minute hard-limit cushion. This is a bounded allowance, not a guarantee that an unusually large artifact upload fits; publication-last preserves the previous accepted head if the new increment cannot be saved. Source setup or GN exceeding the build cutoff still fails closed rather than spending checkpoint reserves.

## Native graph audit refinement after #1098

GN generation succeeded. The strict graph gate exposed remaining shared protocol
bindings and the abstract Ads interface, not the excluded Ads/Rewards engines.
The audit now permits only enumerated generated target variants backed by the
hash-pinned input manifest `removal-compatibility-sources.json`. Any source drift
or unlisted target still fails. This includes News/Rewards/VPN shared protocol
schemas and Ads value/callback types required by surviving NTP consumers.
`AdsService` here is only constructor/destructor/observer interface plumbing;
`AdsServiceImpl`, engine, model, targeting and delivery targets remain forbidden.
This is retained compatibility code, not a claim that every feature-named byte
has been removed. Native build, APK and runtime evidence remain pending.

The separate NTP sponsored-content implementation found during review must be
removed or documented as remaining before claiming Rewards/Ads complete. Merely
allowing interface target names does not prove sponsored-content removal.

### Sponsored NTP follow-up candidate
The paired NTP transforms now compile-exclude sponsored component installers,
static/dynamic/site URL loaders, the Android takeover WebUI resource pack and
rich-media Java classes. Shared NTP services retain regular/custom wallpaper
behavior while sponsor parsing, update scheduling, ad requests, ad events and
sponsor timers are removed from their method bodies. Legacy value declarations
and empty callbacks remain for compatibility. Native graph and DEX gates also
check these extra implementations. This is source/fixture-verified only until
native compilation and actual artifact checks pass; no runtime success claimed.

### Flow #1104: resource-directory ownership repair
All three native removal graph gates passed, but actual compilation rejected
first-run resources excluded from GN while still physically present. The audit
was expanded to the entire composed recipe: 193 pinned resources (183 Android,
10 first-run), covering all affected component removals rather than just the
first reported directory. An explicit path/hash manifest now removes these only
after verifying final owning GN no longer declares them. All checks complete
before deleting any file; shared/retained resources are untouched. Every path is
restored from the pinned source before recipe replay. Chromium's resource checker
remains enabled. Known UI-overlay variants are explicitly hash-allowed.

The failed build preserved 631 changed items in a 119 MiB incremental payload,
then published its experimental head before the honest completion gate stopped
successor jobs. No APK or runtime success is claimed. Regression checks cover
ownership, hash drift, symlink refusal, retained files, and reset/replay; actual
native compilation remains the authoritative next test.

### #1122: final copied NTP resources and private-page VPN promotion

- Real AAPT link failed after 2,125 completed actions: Chromium's copied normal NTP still referenced News icon/include removed from the Brave resource target; private NTP retained a hidden VPN promotional section referencing a deleted VPN drawable.
- Remove the private-page VPN views, matching Java fields/bindings/tint/helper and dangling layout constraint. Keep the two ordinary private-browsing explanatory sections and their icons.
- After the removal recipe, synchronize only the final two audited NTP XML overrides to their actual Chromium build inputs. Do not rerun global branding/preparation or restore removed product resources. Verify exact copies; reject unreviewed new copied-resource inputs.
- Add reset coverage for private NTP XML, pinned fixture/idempotence/drift tests, and final-overlay composition coverage. Source/graph success still does not imply APK/runtime success; a real successor build remains necessary.

### #1124: Android native feature-map compile closure

- Exact commit `962394f` restored #1122's accepted head and all six increments.
- Real compilation reached action 2,866/7,003, then failed in Chromium's Android
  feature-map override: unconditional Leo, News and Playlist feature headers each
  asserted that their now-excluded product was enabled. This is a source consumer
  closure defect, not a cache failure or justification to re-enable those products.
- Remove those headers, Leo feature-map macro/entries, and the analogous Rewards
  and Playlist native registrations. Preserve all retained browser feature entries
  and Origin/payment code byte-for-byte. The exact input and output SHA-256 guards
  fail closed on upstream drift; add this override to the pinned reset manifest.
- Four focused tests and complete removal composition/reset/replay/interruption
  checks pass. APK/native full compile remains pending on the successor; do not
  claim runtime verification from these checks. Native Java lookups should be
  reviewed alongside future feature registration removals.
- Independent consumer review found retained toolbar prediction queried the removed
  Leo native feature. Reject obsolete saved Leo and Wallet toolbar variants while
  preserving Bookmarks/History/Downloads and superclass fallback. Both exact
  pinned input/output digests are guarded, and the predictor is reset on replay.
  Five focused tests and repeated full composition/recovery checks pass.

## Full-only continuation: #1126–#1138 (14 November 2026)

This section is an evidence ledger, not APK acceptance. It supersedes the earlier
Flow-only pipeline wording above: the owner selected Full as the sole build mode,
based on `fc220e7f`, with accepted incremental checkpoint reuse and maintenance.
The older scope/status rows remain historical initial assessments. At this ledger
cutoff, all thirteen groups have source/graph checks, but no new stripped APK has
been produced and verified. Fresh-install, upgrade, UI, network and runtime tests
remain outstanding. No Origin entitlement or payment gate has been bypassed.

### #1126: renderer variable after News removal

- Actual C++ compilation failed on an unused `registry` in the renderer after the
  News consumer was removed (`-Werror`). Acquire the registry only when surviving
  AI Chat or native Web Discovery consumers are enabled; retain the observer and
  unrelated renderer lifecycle. Do not suppress the warning or re-enable News.
- Pinned tests, complete removal replay/recovery, four feature-flag cases and
  independent review passed. Local reviewed fix `efd46c2` was published as
  `98a66b6` for the successor.
- Job3392 saved a 299 MiB increment and accepted-head receipt before the workflow
  ended failed. No APK. A compiler failure and a terminal workflow failure are
  separate events while checkpoint publication is still running.

### #1128: Full verifier still called the legacy driver

- Restore accepted eight increments, but the pre-build shell verifier still used
  the legacy seven-layer driver. This was a pipeline wiring defect, not a corrupt
  accepted checkpoint. No new compilation or increment was produced.
- Point the verifier to `full_driver.py`; keep Full's sixteen-layer limit aligned
  with its sixteen slots and maintenance threshold of eleven. Do not bypass the
  verifier to continue the build.
- Twenty-six Full tests passed, including fresh-process boundaries (0/7/8/11/15/16
  accepted, 17 rejected), integrity failures and actual sixteen-delta replay and
  rollup. Reviewed local `052112d` was published as `b7b25c1`.

### #1130: orphan P3A helper

- The corrected verifier passed after restoring all eight accepted increments.
  Actual compilation then failed on unused `RecordInitialP3AValues` in
  `brave_browser_main_extra_parts.cc`; its reporting callers were already removed.
- Remove the entire orphan definition, including nested desktop code, rather than
  suppressing warnings. Preserve unrelated browser lifecycle/services. Sixteen
  reporting tests and independent review passed; local `3459ad8` was published
  as `9be6ad2`.
- Job3414 saved a 336 MiB increment and a 1.4 KiB accepted receipt: nine layers.
  The final failure gate stopped the failed build only after preserving progress.
  No APK. Action counters are per-run observations, not an ETA or proof of the
  number of remaining source defects.

### #1132: sponsored NTP Java/JNI input closure

- Compilation failed because generated `SponsoredRichMediaWebViewJni.java` still
  referenced `SponsoredRichMediaWebView.Natives`. Removing a shipping Java class
  alone did not remove its JNI generator input in `build/android/config.gni`.
- Exclude that matching generator input using an anchored, checked transform.
  Preserve all other JNI entries, including ordinary wallpaper support; do not
  add a stub or re-enable sponsored content. Five targeted tests and independent
  review passed. Local `2595661` was published as `62d7e05`.
- Job3425 saved a 346 MiB increment and a 1.5 KiB accepted receipt: ten layers.
  No APK. Future feature removals must review Java source lists and generator
  inputs together, not just generated-class/package-name scans.

### #1134: obsolete Ads migration and orphan Leo Java code

- The real build reached linking and failed on undefined
  `brave_adaptive_captcha::MigrateObsoleteProfilePrefs(PrefService*)`, a remaining
  migration caller after the Ads CAPTCHA implementation was excluded.
- Remove only the obsolete include/call. Leave old preferences inert, preserve
  unrelated migrations, and never silently delete valuable user data.
- The same run exposed two Java-analysis warnings left by Leo removal: an unused
  UI context and private tile helper. Remove the known orphan code rather than
  spend a successor run rediscovering those already observed warnings. Bytecode
  adapter compatibility was reviewed; twelve Rewards and five Leo tests passed.
  Reviewed local `d965120` was published as `9ce5870`.
- Job3436 saved a 347 MiB increment and a 1.5 KiB accepted receipt: eleven layers.
  No APK. The next workflow correctly entered checkpoint maintenance before
  compilation at the eleven-layer threshold.

### #1136: maintenance peak-local-disk failure

- Maintenance job3446 merged the eleven inputs into an approximately 8.813 GB
  overlay, but base extraction then failed with `No space left on device`.
  It retained all downloaded input deltas plus their merged copy while extracting
  the base. Ordinary build restore did not have that additional merged copy.
- This is current runner-local disk use, not historical remote APK artifact
  storage. Deleting hosted APK artifacts does not free that runner's disk.
- The bounded fix releases only disposable local input ZIPs after the merged
  rollup has been verified and fsynced, before base extraction. Do not delete
  accepted remote caches, overwrite the old receipt, skip full replay proof, or
  publish without exact remote-cache readback.
- Independent failure-path review and twenty-seven Full tests passed, including
  existing-workspace refusal, corrupt input and extraction failure. Inputs remain
  intact until verified rollup creation; failure must leave the accepted receipt
  unchanged and publish no candidate. Local `1933e79` was published as `4dc9514`.
- #1136 produced neither an APK nor a replacement checkpoint. The eleven-layer
  job3436 head remained authoritative. Local tests did not prove sufficient space
  in CI; that required the successor's actual extraction.

### #1138: verified maintenance publication, no APK acceptance

- Workflow `a5023abf-d813-43cd-b155-d8086a061d3a`, commit `4dc9514`, maintenance
  job3457: released 30.420 GB of local input copies after verified rollup creation;
  eight-shard base extraction passed. Before overlay application, 29.802 GB was
  free against 8.847 GB required. Complete eleven-to-one-layer replay passed.
- Maintenance job3457 subsequently completed: exact new base and increment were
  read back, step161 verified eight shards (`zstd_test=true`) and overlay blobs,
  and step163 published the 1.7 KiB accepted receipt plus previous receipt. The
  eleven-to-one-layer replacement was therefore verified and published, not just
  constructed locally. Root then coordinated cancellation of the following
  removal build stage, which was still restoring its base, to prioritize the
  separately authorized UI-only APK. No compilation/APK was verified in #1138.
- Preserve previous checkpoint evidence after replacement. Daily scheduled
  maintenance and APK-first behavior remain separate commitments; a schedule's
  existence alone does not prove a refresh ran successfully or guarantee cache
  retention indefinitely.

### Reuse and separation rules for future work

- Preserve the exact commits, manifests, fixtures and regression tests when
  pausing this removal experiment. The pre-removal UI baseline is
  `104df3fefd98f22123296d05a2e6540518eb0b6e`; UI overlays24–29 are separate from
  removal overlay30. A UI-only build is a different source recipe, not a claim
  that this removal experiment succeeded.
- Do not merely skip the removal overlay on a restored stripped-product tree.
  Restore/reset the intended pinned source, regenerate the graph, validate the
  exact product recipe and reject stale APK/completion markers. Separate branch
  and checkpoint lineage keep UI-only work from overwriting removal progress.
- Source/native-closure checks and retained compatibility exceptions must be
  reported separately from APK absence proof and device/runtime acceptance.
  Avoid universal “all removed” claims until the relevant artifact and behavior
  checks have actually run.
