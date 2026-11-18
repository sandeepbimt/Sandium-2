# RawS native-menu adaptation (held source prototype)

## Exact base and provenance

Target publication: `sandeepbimt/Sandium-2@e7e782067daef429073e54c2bd8fbb91da7c8439`
(#1396). Its published reviewed tree is `13ed86b7767839afbd62dbed3642ce956a7adaf0`,
identical to local `2bfdcc2cb72deffd9d5e416bfe86068d903cbed3`.
Chromium lock: `158.0.8127.42`, `52bdd21723d5db0c9ab11716d38feac74828cf84`.

This module is **not installed in the APK**. A source-checked explicit adapter now stages native UI/editor/storage integration; it is not called by CI. Feature and patch manifests remain
empty; no CI trigger or native behavior changed. The clean RawS archive is not
replaced. Restore verification is a separate mandatory gate owned by the build
coordinator.

## Native lifecycle findings

Reviewed exact upstream `chrome/browser/ui/android/appmenu/internal/java/src/org/chromium/chrome/browser/ui/appmenu/AppMenuHandlerImpl.java`:

- `showAppMenu` rejects detached window/anchor views, creates the current delegate
  ModelList, attaches observers, sets hierarchy callbacks, registers native view
  binders, computes native dimensions and follows the keyboard visibility lifecycle.
- `onItemClick` checks enabled state, selects/dismisses native AppMenu, and dispatches
  through `mAppMenuDelegate.onOptionsItemSelected` with its original item bundle
  and triggering motion. Do not create parallel action handlers.
- `onStopWithNative` and `onConfigurationChanged` dismiss the native menu.
- Model items can contain nested actions and additional icon actions. A flat list
  of integer IDs is not equivalent to the native model and must not replace it.

## Implemented original model

`RawSMenuModel<T>` is a window-independent customization/pagination model:
- stable symbolic keys, ordered visibility and bounded versioned serialization;
- preserves unavailable entries rather than overwriting the saved layout with the
  homepage's reduced catalog;
- transaction draft: Cancel has no persistence side effects, failed save keeps
  old visible state, only successful durable store writes become active;
- corrupt/newer-version payload presents safe defaults but refuses overwrite;
- generation/identity guards reject stale popup/tab/context clicks and edits;
- policy recheck before native dispatch, at-most-once dispatch, close invalidation;
- bounded/clamped pages with immutable item lists.

New code is independently authored for RawS; no Brave UI source or third-party
browser implementation was copied. Chromium files retain upstream BSD-style
notices when a future patch is made; this module does not relicense Chromium.
No GPL/MPL browser code is imported by this change.

## Added native integration source prototype

- `RawSNativeMenu`: original live policy-filtered native models, existing native
  menu row binders/theme and action dispatch; native appcompat checkbox editor,
  Cancel/Save/Reset, long-press up/down inside native structural groups, keyboard
  Ctrl+Up/Down and row accessibility actions. Checkbox state is remapped with
  reordered rows, not left attached to obsolete indices.
- `RawSMenuStore`: application-owned `raws.menu.layout.v1`, worker-thread durable
  SharedPreferences commit, last-successful committed snapshot visible during
  writes, serialized compare-and-set rejects competing editor lost updates.
- Exact handler hooks dismiss editors on Stop/configuration/destroy and detach
  observers at native popup dismissal. AppMenu window, positioning, animations,
  native gesture input and all original action handlers are retained.
- Important native constraint: `AppMenuPropertiesDelegateImpl` remembers the
  async Read Aloud insertion position. Do **not** shrink/reorder its actual list.
  The adapter instead keeps that source untouched, projects original live row
  models into a separately observed display list, and applies minimal changes
  when the source inserts/removes items. This requires on-device verification.
- Unknown/duplicate symbolic IDs fail closed to an unchanged native list copy.
  Compound/submenu/managed/settings/update/exit rows are not editable. Native
  structural groups and protected rows retain their order. Changes do not create
  missing commands or substitute fake Shields functionality.

`python3 experiments/native-menu/adapter.py --source /path/to/src [--apply]`
validates every exact preimage/postimage and module before writing. It stages Java,
GN and resources; it is opt-in, idempotent and rejects unreviewed source changes.
No tool here triggers CI. Seven files are staged, including English and Hindi resources. Native fixtures retain Chromium BSD-style headers and
LICENSE. Original RawS sources do not import Brave code.

## Incomplete / acceptance gates

1. **Pagination/All Menu is not wired.** The pure model has tested paging, but
   current native UI retains Chromium's list layout and native scrolling. It does
   not yet meet the complete Sandium grid/pagination/no-scroll requirement.
2. Reset, keyboard reorder and accessibility actions now have source implementation.
   English and Hindi resource sets match; other locales fall back to English.
   Real keyboard/TalkBack/visual QA and complete Chromium translation coverage
   remain unverified.
3. No real Android/Chromium Java compile, GN validation, APK or phone testing yet.
   Java UI tests use explicitly limited API doubles, not Android framework classes.
4. Build coordinator must certify #1396 restore and integrate reviewed ownership/
   cache identity. Existing `tools/raw.py verify` intentionally rejects arbitrary
   Chromium changes; it has not been weakened or bypassed.
5. Run native tests for dynamic Read Aloud insert/remove, tab/incognito changes,
   live enabled/managed policy, disabled items, long-press, submenu actions,
   force-stop/relaunch durability, concurrent editors, rotation, IME, repeated
   taps, back cancellation, small screens and native popup animation.

## Native paged-layout route (not implemented)

The existing Sandium layout uses four columns (two at large font scale), eight
quick tiles per page, and an All Menu directory. A vertical native submenu is
**not** an equivalent implementation and has not been substituted.

Chromium's `registerViewBinders`, `customSizingProviders` and
`AppMenuPropertiesDelegate.registerCustomViewBinders` support a custom paged grid
body inside the existing AppMenu popup. This is the preferred investigation path,
not a replacement popup. However `AppMenuDragHelper` selects native ListView rows:
a grid wrapped as one row needs tile-aware drag/cancel handling, or it can dispatch
the body instead of the chosen tile. Accessibility, native menu-button drag,
horizontal paging, long-press/drag editor gestures, repeated taps and native Back
must be verified before claiming the original paged UX is ported. Native sizing
must also accommodate the five-row directory without clipping at large text.

## Evidence

`python3 -m unittest discover -s tests -p test_native_menu_model.py -v` compiles with
Java 21 `-Xlint:all -Werror`, executes model scenarios, writes saved state to disk,
and starts a **separate JVM** to verify restart restoration. Additional tests compile the Android storage adapter and native UI projection
with limited API doubles; validate failed writes and source-index preservation;
and test exact adapter preflight/replay/unknown-source refusal and XML resources.
These are not real Android SharedPreferences, APK, device, native-animation or
visual verification.

## Paged controller increment (unwired)

`RawSMenuPager` now implements the original eight-tile quick-page sequence with
All Menu fixed as its last tile. The All Menu directory includes actions hidden
from quick pages, with five rows per page, four columns (two for large text),
no page-indicator request for a single page, clamped page selection after catalog
updates, and Back returning to quick pages. It does not store or execute the
All Menu control as a native command. Actual protected/compound native rows remain
the host's responsibility; the directory must not invent missing actions.

Each tile is tied to a rendered-page revision and original native action identity.
Page changes, tab catalog changes, dismissal and a successful dispatch invalidate
old handles. Hidden quick actions get a separately issued directory token; they
still pass native enabled/policy checks and cannot execute twice. This is a Java
controller only, not a delivered grid, screenshot or verified gesture behavior.
It is intentionally not included in the source staging adapter yet.

### Exact tile input hazard and required host integration

Reviewed Chromium `52bdd21723d5db0c9ab11716d38feac74828cf84` source:
`chrome/browser/ui/android/appmenu/internal/java/src/org/chromium/chrome/browser/ui/appmenu/AppMenuDragHelper.java`,
`menuItemAction()` and `handleDragging()`.

- Native collection descends **one** LinearLayout level and specially treats
  ImageButton children. A two-row nested grid is neither a normal action row nor
  the recognized native icon strip. Its parent, row containers or labels may
  become targets instead of the desired tile.
- PERFORM sets `didPerformClick=true` after `performClick()` without inspecting
  its return value. A non-clickable grid parent can therefore swallow release
  rather than dispatch the tile or dismiss; merely making parent non-clickable
  is insufficient.
- Native drag selection uses **screen-visible rectangles**, not local bounds,
  and runs only after the pointer exits the menu button. Cancellation dismisses
  natively, and entrance-animation gating must stay intact.
- A safe narrow hook is a typed grid-host interface returning only currently
  visible actionable tile roots. AppMenuDragHelper must collect those roots
  **instead of** the enclosing row, while keeping existing native row behavior
  untouched. Do not recursively collect every clickable descendant: icon/text
  children and overlapping parents can dispatch twice.
- Direct tile taps should call the original native model click handler (with
  ENABLED, bundle and MotionEventInfo intact), not duplicate command dispatch.
  Successful dispatch must use native dismissal. All Menu/pagination are internal
  controls and must not dismiss or call the browser action delegate.
- In-menu horizontal paging must lock one gesture axis after Android touch slop;
  paging consumes the stream and cancels tile press. An anchor-origin drag remains
  native tile selection, not a simultaneous paging gesture. RTL maps direction
  once, at the view boundary. ACTION_CANCEL/multitouch must never perform actions.
- Native custom binder sizing must reserve stable full-grid height on all pages.
  For screens unable to fit five accessible rows, explicitly resolve the size
  constraint rather than clip content or silently add a scroller.

These hooks and actual native custom binder/grid view are **not implemented**.
Next integration must test direct taps, drag from menu button, empty-cell release,
page swipes, cancellation, disabled/rebound actions, accessibility focus, keyboard,
RTL and font scaling on Android. Host controller tests cannot certify those.

## Android grid/view + typed drag hook prototype (unregistered)

`RawSMenuGridView`, `RawSMenuGridBinder` and `RawSMenuTileTargets` now provide an
actual Android LinearLayout-based grid and custom binder, still **unregistered**
with the active AppMenu adapter. They implement 24dp icon roots, uniform labels,
72dp tile rows, four/two columns, native selectable backgrounds, five-row directory,
no empty footer for one page, accessible tile buttons and explicit previous/next
page controls. The existing frozen visual layout still needs screenshot comparison;
these dimensions/native fallback All Menu glyph are prototype choices, not a claim
of exact approved visual fidelity. Text and native themed icons are provided by
host callbacks, not hardcoded site/action substitutes.

`grid_input_adapter.py` separately transforms only the exact upstream drag-helper
collection loop to use the grid's explicitly registered current tile roots. It
preserves native raw-screen hit-testing, entrance/button-exit gating and cancel/
dismiss logic. It is deliberately not part of the existing staging adapter yet.
The grid does not create a popup or navigate pages. Internal horizontal gestures
cancel the pressed child through Android interception; vertical streams remain
native; multitouch/cancel streams are consumed without triggering a tile. Direct
commands return to the provided original native dispatcher. Directory Back has an
explicit `backToQuick()` method requiring native Back integration.

**Still missing before registration:** combine protected native rows and the grid
without changing producer indices; allocate/register a noncolliding custom view
type and sizing provider; update grid on live property/catalog changes; attach
native original action dispatcher (including triggering motion metadata); wire
Back before native popup dismissal; ensure new geometry fits native available
screen space; validate lifecycle and layout on Android. The basic checkbox editor
is not yet the frozen paged Sandium editor. No alternate scroll/list UX is finalized.

API compile evidence: grid/controller/interface compile against Android15 framework
classes from Maven Central `org.robolectric:android-all:15-robolectric-12650502`,
SHA256 `6c0670454f6fcee9f1b17aa393e81d71bf26e7e6ae7c5777ed3924b062191d5b`.
`test_native_menu_grid_api.py` uses this real Android API jar when
`RAWS_ANDROID_API_JAR` is set; the binder's Chromium PropertyModel signatures still
use explicit small test doubles. No Android runtime is executed. The full actual
Chromium GN/Java build remains unverified. No jar is committed.

## Held native-host assembly increment

`RawSGridHost` and `grid_adapter.py` now assemble the existing native popup with
custom type registration, sizing, native producer/protected-row preservation,
source list and live property observers, directory Back and original native click/
long-click routing. The grid type is enabled as an Android ListView container;
its synthetic ID is explicitly refused by the native action handler, so the
container can never dispatch a browser command. Actual child tiles use original
native action models. Peripheral input uses Chromium's OnPeripheralClickListener
and forwards its MotionEventInfo; standard touches/keyboard use the same null
metadata convention as Chromium's native binder. Directory controls stay internal.

Live property refresh is restricted to enabled/title/icon/checked/managed fields,
not CLICK_HANDLER/HIGHLIGHTED/POSITION, avoiding a feedback loop with native model
setup. Observers are detached on native dismissal/destroy. Malformed/capacity or
native view-type collision cases retain native output instead of deleting stored
preferences or inventing commands. This is a fail-closed safety path, not acceptance
of a different final menu UX. Long-click checks current visible tile, current
catalog membership and enabled/policy before returning to native handling.

`grid_adapter.plan(pristine_source)` is a read-only preflight/composition function
for fourteen source files. It does not apply them, weaken the clean verifier,
push or start a build. Native AppMenu tracked keyboard Back first returns from
All Menu to quick pages, then retains original hierarchy/dismissal handling.
**Android15 predictive Back into PopupWindow's OS callback is not yet verified**;
that may need a separate native integration beyond onKey and must not be claimed
covered by the keyboard path.

Additional host tests use limited Android/Chromium doubles to execute insertion,
live enabled/managed-policy changes, directory Back, original action routing and
observer cleanup. Real Android15 API compilation covers grid/view/controller with
small Chromium model/motion signature doubles. Neither test is a complete Chromium
build or native phone runtime test.

Remaining acceptance blockers: full Chromium compile; native popup available-height
and font/RTL/device QA; exact frozen grid/editor visual comparison; native predictive
Back; complete dynamic/lazy native icon/state rendering and checkable action parity;
new controls' accessibility/translation review. The current editor remains the
previous native checkbox prototype, not the approved Sandium paged editor. No
finished or device-ready claim is warranted.

## Native Back/state/editor parity increment

- Exact158 `HierarchicalMenuController.setupBackPressBehaviorForPopupWindow` already
  owns Android13+ `OnBackInvokedCallback` at PRIORITY_OVERLAY and attaches/unregisters
  with the content view. The held AppMenu adapter now supplies its directory-Back
  logic through that existing default-dismiss callback. Native submenu Back runs
  first, then All Menu returns to quick pages, then native dismissal. Keyboard
  Back follows the same order. No competing OS callback or synthetic gesture
  animation is introduced. This is source coverage, not device gesture proof.
- Reviewer-found checked-state loss is addressed: grid checkables have a visible,
  noninteractive native checkbox indicator and RadioButton accessibility state;
  host observes CHECKABLE/CHECKED. Native icon tint, badge and lazy supplier paths
  are delegated to existing AppMenuItemViewBinder branches rather than copied.
- Reviewer-found large-font clipping is addressed at the row level: one shared
  font-metric calculation drives actual rows and native sizing provider, including
  footer controls. Example 18/36/54px line metrics produce72/104/140px row sizes.
  This prevents shrinking text or clipping a two-line label into a fixed72dp row.
- Added the two-quick-row/four-available-row editor body in native AlertDialog,
  local-only draft state, native drag/drop with editor-local token, add/remove,
  keyboard/accessibility reorder, Reset, Cancel and durable Done. A pending Save
  disables Cancel/Back while committing; lifecycle dismissal still safely leaves
  callbacks inactive. Draft changes never write per tap. Pure draft behavior is
  executable-tested; editor/view compile against Android15 APIs with explicitly
  limited AppCompat/Chromium signatures. The checkbox-list editor is not used by
  the held grid assembly. Horizontal quick-page marks replace the earlier text
  page counter prototype, with accessible page controls.

**Unresolved viewport contract:** fixed five directory rows / six editor rows with
large accessibility text may physically exceed a short/landscape viewport once
native protected rows/chrome are included. Font-aware sizing alone cannot make
that fit without fewer rows, smaller text, scrolling or a larger surface. None is
silently declared an approved replacement. Exact device geometry/visual checks and
an explicit acceptable accessibility adaptation are still required before a claim
of universal no-scroll/frozen-layout acceptance. Full Chromium build remains
unverified; source fixture and API-double tests are not its substitute.

The held grid source plan now covers eighteen files. It remains separate from the
active build manifest and does not apply/push/trigger a run on its own.

## Five-row native height policy

All Menu's normal directory remains **five visible rows** (`DIRECTORY_ROWS=5`).
The editor's separate available-actions box remains four rows per the earlier
editor specification; it is not used as an All Menu substitute.

The held AppMenu height calculation now passes its *actual* available content
height, minus protected native row heights, into RawSGridHost. It selects five rows
whenever they fit. Only a physically smaller/large-font viewport reduces the row
count and adds horizontal pages; the same model/provider/view sizing is reused.
Candidate row calculations do not mutate pager revision, so repeated measurements
cannot silently stale otherwise valid click targets. Executable host tests verify
five rows at360px, bounded adaptation at160px, restoring five when space returns,
and repeated measurement preserving live tile handles.

Accessibility exception is explicit: if even one readable tile row plus native
controls cannot fit, native popup overflow behavior remains the last-resort path.
The editor now uses a native ScrollView safety container with scrollbars hidden;
when its fixed2+4 rows fit, it has no scroll range, while impossible short/large-font
windows retain access to all actions rather than permanent clipping. This is not
a claim of unconditional no-scrolling at every accessibility scale. Normal phone
layout must still be visually measured/tested before acceptance.

### Minimum-fit and registry review corrections

If even one grid row plus its controls cannot fit, RawSGridHost now atomically
returns the unchanged native list for that popup session, with stored preferences
untouched. It returns a rebuild signal so native height calculation runs once on
the new native adapter. The two list-observer resize callbacks are suppressed only
during this atomic fallback, preventing nested competing height animations. This
replaces the earlier oversized-one-row escape; no custom row is intentionally
returned above its budget. The accessible native-list exception is not presented
as the frozen grid's normal UX.

Exact `ModelListAdapter.getItemViewType()` requires contiguous types below its
registered count. Grid type allocation now uses `adapter.getViewTypeCount()` after
native/delegate registration, registers binder/sizing, then builds the grid before
show. It does not use the earlier arbitrary custom ID. The Customize menu command
is explicitly protected from editable-row collection, keeping editor access
reachable and keeping that synthetic control out of stored user action keys.

`grid_adapter.plan()` now accepts only known exact pre/postimages, allowing safe
replay after a time-slice checkpoint and rejecting unknown mixtures. It remains
read-only. `verify_applied()` checks all eighteen final postimages and returns their
relative paths/hashes for a future reviewed opt-in pipeline gate. It does NOT
replace the clean baseline/source identity/other-change checks, and no existing
pipeline verifier has been changed. Editor lazy icons use native supplier/binder
paths with view-attached observers removed on detach.
