# Device-feedback toolbar and menu corrections

Based on the five images supplied 15 November 2026, 08:46 UTC. This local
candidate follows the reviewed #1171 UrlBar ownership fix (3dfd828). No CI run
or phone test has occurred for these corrections.

## Exact scope

* Circled tune icon is Chromium's ordinary Page Info icon, not Sandium Shield.
  Select the existing native phone Page Info-in-menu path in BrowserUiUtils.
  StatusMediator still owns HTTP/certificate/permission indicators; this is not
  a blanket hide of security state. Native Brave menu dispatch provides Page Info.
  Existing Sandium Shields artwork, tracer and handler remain unchanged.
* Hide the standalone + and recover its width at inflation and every measurement.
  Keep its native action handler as an internal dispatch target. The existing
  tabs button's short press invokes that handler (including private-mode selection).
  Holding invokes the original native switcher callback and consumes the release.
  Original tablet behavior stays unchanged. Native transition and restore guards
  govern both actions. Preserve tab count/notifications; add a small adjacent +
  badge, action descriptions and accessible click/long-click labels.
* Change only location_bar_url_text_size from 16sp to 14.4sp. No global scale,
  touch-target reduction, formatted-URL change or editable-text alignment override.
* Remove All Menu and its redundant expanded mode. Keep specialized-action native
  drill-down and Back. Replace the header + with Edit; remove the editor title
  but retain Cancel/Done. Both menu and editor use identical 20dp indicators,
  with an 8dp visual gap when two pages, inside separate 48dp touch targets.
  More-than-two-page customization retains scrollable native-sized targets.

## Composition and safety

New overlay runs after unified address and its intermediate contract checks.
Chromium reset paths include all four added modified files, and the full
UI/removal reset/replay fixture harness runs the new overlay. No checkpoint,
seed, build mode, branding, home, navigation, player or removal-scope change.

Not included here: the still-open blue-flash diagnosis, keyboard-following focused
bar diagnosis, and the separate search-provider/engine-strip changes.

## Verification

Seven transform/contract tests pass. Existing eight unified-address and six
motion tests pass, plus paged-menu pinned-source transforms. Full pinned
UI/removal composition, reset/replay, interrupted-removal recovery pass.
These are not an Android compile, real click event test or visual/device test.

Before APK delivery, real Full compilation and artifact inspection remain needed.
On phone test ordinary HTTPS versus HTTP/certificate errors, Page Info via menu,
Shield, short/long tab press, normal/private mode, restored tabs, rotation/RTL,
TalkBack, dynamic font size, repeat/cancel menu edits and native submenu Back.

Uncatalogued conditional native controls retain a conditional Original controls
escape hatch. It is absent for the normal fully catalogued menu; neither All Menu
nor the rejected default-browser action is reintroduced.
