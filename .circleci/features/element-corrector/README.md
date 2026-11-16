# Element corrector renderer core (NOT ENABLED)

Run `node --test .circleci/features/element-corrector/tests/corrector.test.mjs`.

This source is not in the app build or feature-application pipeline. Tests exercise a fake DOM and bridge, not Chromium, Mojo, Android, native stylesheets or persistence. It is not a working user feature.

Implemented: bounded structural selector generation; only foreground/background and opaque RGB; rejection of active, embedded, root, shadow and SVG targets; separate preview/saved-sheet contract; cancel, mutation revalidation and close; explicit browser session validity checks at every mutation entry.

Unimplemented hard gates:
- Native Mojo handler deriving origin and primary document identity, browser-owned session/cancel/Save UX.
- Keyed InsertStyleSheet/RemoveInsertedStyleSheet bridge with atomic replacement.
- Profile-owned, non-sync exact-origin saved rules and private-memory lifecycle (never adblock filters).
- DOM mutation subscription and anti-retarget strategy. A structural selector can match a different node before mutation revalidation; this core alone must NOT ship persisted rules. Fingerprints mitigate accidental changes but are not a node-security identity.
- Stronger renderer-to-browser serialization validation; native cannot trust JS validation.
- Packaged isolated-world loading without page-importable bindings, picker gesture integration and lifecycle navigation tests.
- Forced-dark renderer ordering, device screenshot tests, accessibility and compiler verification.

Do not expose a Shield button until all functional consumers exist. The module's bridge object is an isolated native interface contract, not authorization to bind page-owned JS methods. Native Save must be independent from renderer event claims.

## Identity review revision

The initial sheet bridge is superseded. Live selections now return opaque session handles retaining the actual Element. Preview and confirmed application reject same-tag/same-ID replacement objects. Revalidation removes stale overrides and handles; it never reacquires a new matching element. The native bridge must apply typed foreground/background RGB to exact node handles, NOT CSS selectors or mutable DOM attributes. Existing compileRule output is a validation/test helper, never passed to the native bridge.

Automatic persisted selector rebinding is deliberately removed. Until a reviewed cross-navigation matching design exists, remembered values may be offered for explicit selection/confirmation in a new document, not auto-applied. This is a limitation versus the requested remembered per-site feature, not a silently changed requirement. No native node-bound override consumer is implemented yet; a CSS-only native implementation would reintroduce the bug and cannot enable this feature. Form/button/contenteditable containers are now excluded.

## Second review revision

Removed CSS generation entirely; validateRule returns only a validity result. Confirmed application now calls one atomic native commitSavedAndClearPreview transaction and updates JS state only on successful return. Reconfirming the same node/property replaces its prior value rather than consuming rule capacity. The native design document records a proposed document-owned node override registry and conservative unique-ID remembered matching. Neither native registry nor remembered matching is implemented.

## Native source draft (not compiled or enabled)

An actual document-owned weak-node registry is now drafted in native/sandium_element_colors.{h,cc}. Offline apply-native-draft.py composes exact pinned Element detach hook, uncacheable style consumer, WebElement public entry points and BUILD sources. No Mojo/Java/Shield entry point calls these methods. No persistence or browser authorization/session code exists yet. Page darkening may subsequently transform these chosen colors; ordering needs real renderer tests. The prototype is NOT safe to expose just because source composition passes.

Fetch pinned/hash-checked test sources with tests/fetch-native-fixtures.py, then run tests/test_native_composition.py. Two tests check repeatable source composition and failure-before-write on missing anchors. They are not C++ compilation, GC/lifecycle or rendering tests. The source subset gap is partly resolved by the fixture fetcher; the missing native build toolchain remains.

A separate C++ rule-store draft now validates bounded typed records and scopes keys to canonical HTTP(S) origins. Private constructor deliberately discards PrefService and reads/writes only its own memory map. It is not registered, profile-lifecycle-owned, compiled or called yet. Native review found atomic-move cached-style and eligibility revival concerns; source draft now requests recalc for state-preserving moves and purges corrections after observed eligibility loss, but executable Blink tests are still required. Container targets with form/embedded descendants are conservatively rejected to avoid inherited foreground changes; no CAPTCHA-preservation claim is made.

## Browser session and remembered-rule draft

Native element_color_session now captures WeakDocumentPtr and browser-derived committed origin, requires visible active primary frame, authenticates selection sender/session token, and cancels on committed navigation (including same-document), hiding and WebContents destruction. Only browser-owned UI callbacks may invoke Save; renderer acknowledgment is rechecked against the current document before profile storage. Profile store lifetime is attached to Profile user data, keeping off-record instances separate and destroying their in-memory rules with profile. No original-profile fallback occurs.

The transport is an abstract native interface, NOT implemented Mojo wiring. Session/prefs are not in BUILD or registered; no Java UI calls them. A missing acknowledgment has no timeout yet, and closing UI must handle cancellation rather than waiting on a destroyed weak callback. These are live integration blockers, not passing behavior.

The JS matcher now supports one explicit browser-triggered restore pass: bounded unique ID + tag/role + exact ancestor fingerprint, no anonymous targets, no ambiguous matches, no repeated attempt or reacquisition after replacement. This is heuristic identity across documents, not proof of semantic identity. Matched nodes bind to exact node overrides; automatic header/logo detection remains absent. 19 JS tests pass; native code remains uncompiled. The matcher is not yet connected to native transport or persisted records.

## Transport/registration draft

Added a dedicated ElementColorAgent Mojo interface and browser-side associated-remote transport, keeping the blocker Agent receiver separate. Offline apply-browser-draft.py composes the Mojo declaration, Android-only browser sources and non-sync profile preference registration. Source composition was exercised twice against pinned Brave files. A five-second Save acknowledgment timeout and cancellation result handling now prevent indefinite pending Save. These source patches are still NOT in production pipeline.

Renderer receiver/bindings, selection-to-browser callback and Android native chooser/Shield entry remain unfinished. The declared Mojo interface currently has no renderer implementation, so registering the browser source alone does not produce a functioning feature. Native compiler verification remains unavailable locally.

## End-to-end source wiring draft

Added real renderer receiver, separate Agent binding, isolated-world manual overlay, exact WebElement selection, browser receiver authentication, request-generation JNI adapter and profile-backed restoration at DOMContentLoaded. Browser transport clear now removes current document overrides on Reset. Cancel removes preview/picker but preserves committed overrides. UI callback generations match the separate Android chooser work. Offline source compositions were run twice against the pinned Brave source subset; 19 JS/2 composition tests pass.

This is source wiring, not a verified executable implementation: Android chooser is owned by the coordinated dark_impl branch and must be composed/reviewed together; native/generated Mojo/JNI code has not compiled; BFCache restoration and post-load dynamic targets are not covered; automatic restore does one conservative initial-document match only. Pipeline remains unmodified. No claim that the feature appears or works in an APK.

Review corrections: preview now rejects adopted nodes from another document; cleanup targets the captured document root. Remembered wire property is canonical integer 0/1, tested against a native-shaped JSON fixture. Begin uses a distinct lifetime weak pointer plus generation check across reentrant cancellation callbacks. Native Commit revalidates ID/tag/role/ancestry against the exact selected node before acknowledging a save. Five source-guard checks cover these structures and private-pref exclusion; they are not executable C++ behavior tests. Java chooser is now included from coordinated commit d4136b3 with 17 actual-Java assertions using Android/JNI stubs. Manual paint/palette ordering still awaits renderer composition and review.

Manual paint integration now requires renderer commit 5e4c4bb contract. Native composition fails if the final ApplySandiumPaintPolicy anchor is absent; manual override applies immediately afterward and sets inherited SandiumManualColorOverride, clears palette enable and native forced-dark. The renderer honors that flag by disabling both palette and stock automatic filtering for the manually corrected subtree. Exact combined-source/device validation remains mandatory. Component transform tests use a synthetic prerequisite anchor and do not claim full renderer composition success.

Session shutdown now invalidates lifetime callbacks before cancellation and rejects new Begin calls during destruction. Navigation restore has a lifetime/generation guard around synchronous cancellation callbacks. BFCache/prerender activation now explicitly re-invokes the one-shot restoration path because DOMContentLoaded need not fire on activation; this is a source implementation requiring actual lifecycle tests, not a verified device outcome.

### #1201 strict descriptor JSON options
The pinned JSONReader API requires an explicit options argument. The sole
manual-corrector ReadDict call now uses JSON_PARSE_RFC, matching the picker's
JSON.stringify payload and rejecting comments, nonstandard escapes and invalid
Unicode rather than enabling Chromium-extension parsing. The existing parser
depth default and post-parse validation remain unchanged. A compile regression
uses the actual pinned json_reader.h and the extracted production call, with an
old-syntax negative control; dependencies are stubbed, not a full native build.

### #1203 Chromium complex-class special members
MojoElementColorTransport now declares an explicit constructor and virtual
(overriding) destructor in its header, with both defaulted out of line in the
existing translation unit. This addresses the actual chromium-style diagnostics
without disabling warnings or changing endpoint ownership/member cleanup order.
The adjacent session, renderer and rule-store types already have out-of-line
special members. Source guards and full overlay replay cover the declarations
and definitions; only an authorized Chromium build can rerun its style plugin.
