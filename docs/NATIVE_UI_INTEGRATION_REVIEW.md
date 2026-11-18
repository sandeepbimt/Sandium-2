# Held RawS native UI integration

## Current status

The dated-by-commit entries below retain earlier investigation states. They are not current blockers unless repeated here. The native manifest is active locally; strict feature verification, apply hooks, recipe identity, certified #1396 seed admission and completed-progress recovery are implemented. Full host tests: 209/209 with the Android15 API fixture. Independent final runtime review and authenticated CircleCI configuration validation remain required before launch. No new Chromium build, live cache recovery or device acceptance is claimed.

The coordinator has explicitly accepted the accessibility fallback **for this experimental build only**. Universal five-row/no-scroll behavior remains incomplete and must be reported as such.

Candidate starts from e7e7820 and combines menu chain through 874f1b5 and native-toolbar chain through 36bd6dc. Service #1396 source commit is independently confirmed as e7e782067daef429073e54c2bd8fbb91da7c8439; accepted archive confirmation remains a separate gate. A common Git base alone is not archive certification.

## Verified locally

- Both chains merge without file conflicts.
- Menu host suite: 13 tests, 12 passed and one Android API compile skipped because RAWS_ANDROID_API_JAR is unavailable.
- Toolbar suite: four tests passed, including limited Java paint harness.
- These are fixture/model/API-double checks, not full Chromium compilation, Android device geometry, or runtime smoothness validation.

## Acceptance differences

- All Menu normally uses five visible rows. Short/large-font windows can reduce rows and horizontally paginate. If even one readable row plus native controls does not fit, the native list replaces the custom grid for the popup session.
- The editor has a ScrollView safety container. Thus the candidate does not implement an unconditional five-row/no-scroll policy on every device/accessibility setting. Do not silently treat this exception as user approval.
- Toolbar adapter changes native-owned paint only. It does not port the entire Sandium toolbar, add a Shields engine, force adaptive controls visible, or redefine native navigation ownership. Tablet remains native.

## Production activation blockers

- Current tools/raw.py verifier intentionally admits only the exact Siso compatibility modification. It must gain exact feature postimage verification, not have its clean-source gate disabled.
- sandium/features/manifest.json remains empty. No pipeline apply hook is installed.
- Current compatibility fingerprint covers patches/features and selected core helpers, but not these experiment adapters or menu implementation files. A reviewed explicit recipe/ownership inventory must cover active code before reuse.
- Need combined preflight/replay/tamper tests, source identity and unexpected-change checks, production compilation and device acceptance.

No CI or publication is authorized by this document. Full Brave upgrade remains separate and held.

## Local activation infrastructure, still opt-in disabled

`tools/native_features.py` now reads the existing feature manifest and validates exact combined pre/postimages with all generated outputs required. `raw.verify` still checks pinned source/version and rejects unrelated tracked changes; only explicit preparation accepts reviewed preimages. Compilation applies the complete preflighted plan, verifies it, then verifies again after runhooks before GN. Recipe identity includes active adapter, fixture and implementation inputs. The manifest remains empty until reviewed seed admission and activation.

Independent Android15 API compile subsequently passed with the shared API jar; Chromium API doubles remain a limitation. Combined20-file replay/tamper test passed. Eleven feature boundary/identity tests and20 baseline tests passed after the new recipe identity was generated. Service/archive compatibility is not inferred from these tests.

Full integrated host suite at50ebc52:147 tests passed in22.101s with RAWS_ANDROID_API_JAR enabled. The suite includes small fixture checkpoint round trips, not production archive acceptance or full Chromium compilation. Independent integration review and explicit seed admission remain pending.

Independent review identified an admission gap: ordinary restores could accept known preimages and silently repair missing feature files. Corrected admission now requires exact postimages by default; only a stage1 fresh marker with exact current scope/workflow and no selected/restored proof admits preparation. A cross-recipe baseline seed still needs a separate verified path. Admission and compile/source hook implementations are themselves included in the recipe fingerprint. Twelve feature/admission tests and20 baseline tests passed after this correction.

## Active local candidate verification

Both reviewed modules are now explicitly enabled in this isolated candidate manifest to exercise actual opt-in preflight. This does not publish or launch the candidate. The active-manifest full host suite passed199 tests, including Android15 API compilation with limited Chromium doubles. One baseline checkpoint fixture was corrected to select the appropriate explicit build branch rather than assuming an empty feature manifest.

Exact #1396 transport, real isolated callback commands, current-workflow prepared promotion, and explicit incomplete same-recipe resume are staged. Completed-progress archive-only recovery and final service-level pipeline review are still in progress. No actual full Chromium build or device acceptance is claimed.

## Final recovery integration review

The active native candidate now includes a separate completed-progress recovery route: exact same-recipe receipt, fresh source/GN/signed-APK validation, full archive, then fresh probe, with no compile slices. Missing baseline Git objects are fetched only by exact pinned SHA from the CI-verified repository origin, with a bounded deadline and identity verification. Normal Full job definitions remain structurally unchanged.

The combined host suite passed 209 tests (including the optional Android API test when supplied). These results do not establish service-level CircleCI configuration validity, live large-cache restore, new Chromium compilation, or device behavior. Independent final review and authenticated CircleCI validation remain launch gates. Existing five-row accessibility exceptions remain unresolved acceptance limits.

## Reviewed experimental candidate

Final integrated active suite: 215/215 passed with the Android15 API fixture. Independent review passed 11 generated-pipeline tests and five restored-JDK tests. Pre-restore source tests now use explicitly installed host Java21 with bounded setup; actual APK verification uses the restored Chromium DEPS-managed JDK, without host fallback. ZIP/manifest/ABI rejection remains before external runtime invocation. Normal Full structural preservation and generated shell/Python syntax checks pass.

Source review is clear for authenticated service configuration validation. No launch or successful GN/Android lint/device/live-cache claim follows from this readiness status. The five-row accessibility fallback is approved only for experimental testing.
