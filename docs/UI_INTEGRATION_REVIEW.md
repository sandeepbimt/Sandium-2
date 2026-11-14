# Sandium coordinated UI integration

Local review branch only; no publication, CI build, Android compile, or device certification.

## Protected baseline

Based on #1144 source tree (local `507d647`, shipping tree `e16ba155`). `.circleci/config.yml`, Full driver/bridge, source pins, checkpoint namespace/branch guard, maintenance and APK export ordering remain unchanged. The removal branch and checkpoint are untouched. Existing logo artwork and balanced Shields tracer are not replaced.

Overlay-29 runs the existing prune/identity/theme/status/popup sequence, then native bottom toolbar and model-backed paged menu. Each new overlay has a post-apply contract against the actual restored source. Strict wiring verifies exact command order and arguments; manifest hashes cover new source/resource files and changed wrapper. CI must still run on `experiment/sandium-ui-only`; this local branch does not relax that guard.

## Evidence and limits

- Strict wiring 20 tests; UI-only product/scope 7; Full pipeline/checkpoint 27; bridge pipeline 3 passed.
- Theme 9, status 9 and welcome patcher/idempotency checks passed.
- Pinned-source composition exercises overlapping branding/tracer, prune, theme, status, toolbar and menu transformations in actual order twice. This is a focused fixture composition, not a complete Chromium checkout or Android build.
- Baseline aggregate had 129 tests: 128 passed and pre-existing `test_single_pipeline.test_disk_guard_fails_closed` errors because `driver.disk_guard` was removed. Pipeline code is not changed to accommodate this stale test.
- Runtime/device gates remain: menu dragging/paging/accessibility, native submenu/back flows, bottom omnibox/IME/RTL/rotation, cached feature state after upgrade, status transitions and cross-screen theme rendering.
- Explicit dynamic-color preference remains honored. Websites, security/error semantics, private branding, system dialogs and externally controlled surfaces are not blanket recolored.

## Final review gate

Menu-local day/night resource closure and bounded native hierarchical activation are integrated. Top/bottom theme providers retain native paired surface/tint behavior for regular browser chrome. Final independent review remains required. Do not claim exact Edge interaction parity or app-wide visual verification from source tests.

## Final coordinated revision

Integrated independently reviewed native-icon tint/badge/lazy-supplier fix and reduced-motion-aware content fades. Menu backdrop stays opaque; 120ms child-content transitions preserve in-progress alpha across same-screen refresh. Native/system/reduced-motion and low-end guards remain. Welcome content and Settings entry are covered; this does not claim every inherited popup, toggle, or activity now has a custom fade.

Final aggregate: 131 tests, 130 pass; same baseline-only missing disk_guard API test error. Motion5, chrome-provider5, theme9, status9, UI-scope7, wiring20 and menu fixture/idempotency tests pass. Final composed pinned transformations pass twice. Native Android compilation/device rendering still pending CI/device testing.
