# #1148 Start browsing crash: menu drawable type contract

## Evidence
User installed #1148, commit `3dfd3fc5443f63bebf5bb2869d84eacdf33a9496`.
Their bugreport dated 2026-11-15 01:10:15 local records four repeated main-thread
failures from 01:08:56 to 01:10:01 in `ChromeTabbedActivity` initialization:

`ClassCastException: VectorDrawable cannot be cast to BitmapDrawable`

Top frames: `org.chromium.chrome.browser.toolbar.menu_button.MenuButton.b` and `.C`.
The raw report is not committed because it contains unrelated personal device data.

Pinned Chromium `d331de35ca8ab1358c7a17e4bd41627d55eaef51` MenuButton.java
unconditionally casts both cloned menu and badge drawables to BitmapDrawable in
`updateImageResources()`, called on initial tint and layout. Our new hamburger XML
uses a VectorDrawable. This is a concrete resource/consumer contract mismatch,
not a filter activation failure or a reason to clear user data.

## Fix and preserved behavior
Keep the live vector hamburger and native button. Convert only the private
animation drawable to a bitmap when necessary. Existing bitmap drawables still
use the native fast path. Clone with resources and preserve state, level and layout
direction. Rasterize at intrinsic pixel size with matching resource density;
the existing bounds, CENTER gravity, tint, alpha and badge code stay intact.
Only a copy is drawn; original drawable bounds and live ImageView tint are untouched.
The fallback 1px minimum guards invalid dimensions, not a promise of support for
arbitrary intrinsic-size-less drawables. The actual hamburger has explicit 24dp.

## Validation and limitations
Pinned source transform/idempotence, changed-anchor failure, resource XML,
density/state/tint/interaction contracts and UI-only source manifest tests pass.
Independent review checked bitmap preservation, live drawable isolation, density,
state, tint and tab-switch animation contracts. This environment has no Android
runtime or Java compiler. Source tests cannot prove device startup or animation;
the next APK must be tested for Start browsing, ordinary/incognito launch,
rotation, menu and tab-switch transitions. No CI job was started by this fix author.

## Prevention
An XML resource substitution is not safe solely because it compiles. Audit its
native consumer's drawable assumptions and exercise activity startup after all
first-run screens. Keep upstream-specific casts in regression checks.
