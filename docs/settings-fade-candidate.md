# Settings fade candidate (after #1175)

## Evidence and change

The pinned Chromium SettingsActivity calls shared X-axis enter/exit animations for both TWEEN and PROPERTY fragments. The earlier Sandium native-theme overlay adds a second view-alpha animation but leaves those slide animations intact. This explains a source-level mechanism for the reported slide; no device recording was analyzed by this worker.

This overlay changes only Settings-owned transitions:
- Native Settings fragment transactions use scoped alpha-only XML resources (100 ms entry, 80 ms exit) for forward and pop transitions. Native animation-type selection, back stack, routing, and saved state are unchanged.
- Disabled system animators select zero animation resources when the transaction or activity transition is configured. Toggling animator scale after a fragment is already on the back stack can leave an earlier stored tween pop animation; runtime rechecking of stored pop animation is not implemented.
- Removes the earlier posted view-alpha hook, avoiding a third view animation and leaving existing background/inset callbacks intact.
- BraveSettingsActivity configures its activity transition on API 34+ and uses legacy pending-transition calls on older supported Android, without delaying finish or intercepting Back. The native close-menu action keeps its reorder-to-front navigation and overrides the immediate pending window animation after startActivity.
- Resources are registered in Brave's existing Android resources target. Global shared X-axis resources are not modified.

## Integration contract

Wiring included in this candidate: `apply-sandium-settings-fade.py --src "$SRC" --core "$CORE"` and its `--verify-only` invocation after native-theme in product-overlay-29-0, preferably at the end, then `test-sandium-settings-fade.py`. The exact flow-wiring sequence is updated. Added Chromium `chrome/android/java/src/org/chromium/chrome/browser/settings/SettingsActivity.java` to both full and UI-only restore inventories. No pinned Brave patch exists for this path (GitHub 404 checked at pinned Brave commit). BraveSettingsActivity is already in both inventories; android/BUILD.gn is already in the full core inventory and is now added to UI-only reset as well. Source composition replay includes the new transform and checks its markers. Generated scoped resources are rewritten idempotently.

Pinned Chromium: d331de35ca8ab1358c7a17e4bd41627d55eaef51.
Pinned Brave: 44a84b1f89d9a35287289d6a3d493e362f5a5123.

## Validation and limits

Six local source/XML/integration contract tests pass, including exact transform anchors, idempotence, reduced-motion guards, resource registration, lifecycle-tail preservation and absence of translation/scale. This is not an Android compile, instrumented transition test, emulator or device test. Full pinned UI/removal composition, reset/replay, interrupted-reset recovery and corrupt-patch rejection also passed locally. Independent source review remains in progress. Device checks: initial Settings open, nested Privacy Settings, Back and toolbar Up, close-settings action, rotate/recreate, system animation scale zero, Android 13 versus 14+, tablet/multi-column behavior. Platform predictive back and the close-settings reorder-to-front path require device verification. Existing Settings AnimationType.NONE stays unanimated deliberately. This candidate does not add motion to unrelated app popups or web content.

## Fixture provenance

SettingsActivity.java fixture is Chromium source at the pinned revision (BSD-style license, copyright header retained), from https://github.com/chromium/chromium/blob/d331de35ca8ab1358c7a17e4bd41627d55eaef51/chrome/android/java/src/org/chromium/chrome/browser/settings/SettingsActivity.java . BUILD.gn fixture is Brave source at its pinned revision (MPL 2.0, header retained), from https://github.com/brave/brave-core/blob/44a84b1f89d9a35287289d6a3d493e362f5a5123/android/BUILD.gn . Existing BraveSettingsActivity fixture retains its original provenance/header.
