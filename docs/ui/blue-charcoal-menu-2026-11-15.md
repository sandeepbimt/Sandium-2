# Blue / near-AMOLED revision and paged-menu motion

Base: #1169 `d6b31ba6165ab4afccdaef815236302c906c2805`.
Scope: app-owned native theme, welcome, Settings root, normal/edit paged menu.
Status gradient is a separate change; no source/checkpoint/CI configuration changed here.

## Reference evidence

Inspected the four supplied photographs/screenshots and 4.916-second Edge video.
The arrow crop's dominant blue pixels are RGB(110,142,181), `#6E8EB5`.
The Sandium screenshots show gold controls, neutral-grey top four icons and
Make Sandium default still present in the editor. The Edge video shows the action
grid sliding horizontally while its upper four library actions stay stationary.
This implementation is original native Android code, not copied Edge source.

## Palette

- Dark root `#080808`, card `#101010`, raised control `#181818`, highest `#202020`.
- Dark interactive blue `#6E8EB5`; on-blue content `#080F18`.
- Light-surface interactive blue `#365D86` for readable contrast.
- Welcome checked-track `#203D58`; existing off-state and success semantics stay intact.
- Blue/card contrast 5.62:1; on-blue/blue 5.68:1; light blue-role/light raised
  surface 5.59:1; welcome checked thumb/track 3.32:1.
- Original logo, tracer, error/security/success/statistic color families unchanged.
- Explicit dynamic-color preference remains respected. This is the baseline,
  not an override of a user's already-enabled dynamic palette.

Settings previously calls `SemanticColorUtils.getSettingsBackgroundColor`, not
Brave's container resource. New helper paints the Settings activity/root fragments
with the dark baseline when night mode is active and dynamic colors are off.
Light and opted-in dynamic modes keep the semantic color. It never traverses and
recolors cards, security controls, arbitrary children, or web content.

## Menu behavior

The default-browser promotion is excluded in both product restriction policy
(including native fallback/tablet/customize catalog) and phone menu catalog.
Old checkpoint policy helper is upgraded; existing layout reconciliation filters
removed entries. Android/Settings default-browser functionality is not removed.

The four fixed library icon glyphs use blue; their labels remain readable normal
text. Editable Exit remains ordinary customizable content.

Page indicators are short horizontal rounded strokes in 48x48dp focusable targets,
with accessible page labels and selected state. Page count is not hard-coded to
two; the selector strip can scroll horizontally for large custom layouts.
Click/keyboard/TalkBack selection and dragging onto a destination indicator are
alternatives to swiping. Keyboard/accessibility focus on an indicator is restored
to the destination indicator after page replacement.

Normal and edit modes accept horizontal swipes starting inside the action-grid
viewport. Vertical scrolling, the available-actions editor area, and selector
scrolling are not hijacked. Actual icon dragging suspends swipe interception.
Outgoing and incoming grids slide over 180ms, RTL-aware, with the fixed library
row and heading stationary. The outgoing grid is disabled and hidden from
accessibility until removed. Generation/cancellation guards clean up on repeated
navigation, refresh, dismissal or reduced-motion settings. Disabled system
animations use immediate placement, not a forced animation.

## Verification and limits

Passed theme 13 tests (including actual pinned Settings fixture/migration), motion
6 tests, full welcome transformation checks, pinned paged-menu transformation
and checkpoint migration/idempotency checks, removal overlay sync 3 tests,
browser-crash regression 9 tests, Python compilation and diff whitespace checks.
An actual five-file already-patched native-theme fixture also applied twice with
byte-identical second output. Independent source review requested and completed.

No Android build, emulator or device test performed. Local `javac` is absent;
existing standalone Java menu-state test could not run. Source contracts are not
proof of native compilation, frame pacing, TalkBack behavior or every settings
subscreen. Test fast repeated swipes, cancel/save editor, drag between pages,
large fonts, RTL, reduced motion, long selector strip, light/dynamic theme, and
Settings subscreens on device before describing them as verified.

Integration must update the coordinated UI product manifest hashes for changed
registered inputs. Leave other worker branches intact and integrate homepage
accent changes separately. Do not trigger CI from this isolated change.
