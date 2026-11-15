# Unified Sandium address bar candidate

Base: #1169 d6b31ba6165ab4afccdaef815236302c906c2805. Isolated local work; not published or compiled.

## Scope

- One painted surface enclosing native toolbar actions. Existing editable omnibox is retained, not replaced with a synthetic URL view.
- Native vertical-dots menu asset. Existing vector-animation raster-copy fix remains necessary.
- Actual Sandium Shields row moved ahead of URL, retaining existing drawable/animated tracer and native handlers. Standard Page Info / security indicator remains a **separate native control**, unlike the simplified concept image; Shields must never imply connection security.
- Selected search engine icon comes from existing pinned StatusMediator/SearchEngineService observers on NTP and focus. No hardcoded Google icon and no extra favicon fetch.
- Ordinary non-rewritten HTTP(S) resting text uses native formatUrlForDisplayOmitSchemePathAndTrivialSubdomains. Native URL data keeps full formatted editing text. Earlier offline/frozen/publisher/special scheme handling untouched.
- Reuses upstream LocationBarPhone packed status+URL centering, native safe long-origin start alignment/horizontal scrolling, and focus restoration. No custom hostname split, middle ellipsis, or IDN conversion.
- Native focus, selection, keyboard, voice and suggestion controllers retained; no manual keyboard-height observer. ToolbarPositionController is routed to retain preferred-bottom placement while omnibox-focused, reusing its existing focused-bottom IME offsets and resize/max-height handling instead of the old forced-top focus condition. Explicit top preference, Hub, Find and PiP native fallbacks remain. This is an implementation strategy, not evidence that keyboard motion exactly matches the reference on a device.
- Below 360dp, or font scale above 1.3, the New tab convenience button collapses to give identity adequate space. New tab remains exposed by the existing paged app menu. Forward remains in the bar. The 48dp native centering side reserves are removed because the real external actions were already subtracted by ToolbarPhone, preventing a redundant 96dp identity-space loss. Other targets are not shrunk below their native sizes. This responsive exception differs from the full-width concept and needs device verification.

## Composition

Run after apply-sandium-bottom-toolbar.py and its source tests, after existing UI/removal overlays. New source test must run after this overlay. Earlier bottom-toolbar exact-output assertions intentionally describe its own intermediate output, not this later layout. Not yet registered in the pipeline pending independent review.

Pinned source versions are inherited from bottom-toolbar module: Chromium d331de35ca8ab1358c7a17e4bd41627d55eaef51, Brave 44a84b1f89d9a35287289d6a3d493e362f5a5123. The fixtures are original Chromium files at that commit, under their original BSD notices.

## Validation status

Seven source/transform tests pass, including idempotence, early URL branch preservation, explicit display/edit separation, native overflow behavior and XML child draw order. These are NOT Java compilation, JNI/native formatter execution, screenshots, touch tests or Android device tests.

Required before delivery: real pinned Full compilation, independently inspect rendered output, test NTP-to-web-to-NTP, same-tab navigation, blank/focused typing, Back/IME dismissal, repeated focus interruptions, tab switcher transitions, incognito, dark/light, portrait/landscape, RTL, split-screen, large fonts, multi-window. Verify deceptive long hosts, public/private suffixes, Unicode/punycode IDNs, IPv4/IPv6, ports, HTTP warnings and certificate errors, and non-web schemes. Verify touch and TalkBack ordering and no Shield click leaking through focused field.

No checkpoint, navigation fix, player, home shortcut, or 13-removal source changes are included.

## Independent review corrections

- Leading controls now follow BOTH the refactored background View and the legacy location-bar background painter in normal XML child order. The separate drawWithoutBackground animation path also draws Forward/Shield once, after drawLocationBar.
- Responsive measurement runs only after the native destroyed-dependency early return.
- Shield wrapper becomes INVISIBLE immediately while the omnibox is focused, retaining its measured space but excluding its descendants from hit-testing. Both state/measurement and background-paint paths enforce this rule, including measures without background recalculation. The native field and other controls retain their transitions; the Shield itself does not visibly fade on focus acquisition, prioritizing unambiguous input ownership.
- Post-apply verification is available with `apply-sandium-unified-address.py --src "$SRC" --core "$CORE" --verify-only`; it is read-only and detects incomplete transforms/resources. This is still a source check, not a runtime test.

## Pinned Brave position adapter

The pinned Brave tree has no textual patches for LocationBarModel, LocationBarPhone or ToolbarPositionController; those reset inputs are the exact Chromium fixtures. Its existing bytecode adapter routes calculateStateTransition through BraveToolbarPositionController, which passes `false` for NTP/tab-switcher flags and forwards the omnibox focus flag to Chromium. This overlay leaves that adapter unchanged. Thus the upstream guard preservation above describes source-level compatibility, not a promise that Brave retains Chromium's Hub/NTP placement policy. Actual inherited Brave placement still requires device testing.
