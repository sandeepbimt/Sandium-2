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
