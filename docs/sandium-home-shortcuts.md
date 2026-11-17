# Native Sandium home shortcuts

Base: #1169 `d6b31ba6165ab4afccdaef815236302c906c2805`. This change does not publish or start CI.

## User-facing behavior

- A five-column shortcut grid sits above the bottom toolbar, with its last row above a 48dp chevron target and an 8dp toolbar gap, rather than assuming a physical inch on every display.
- Up to 20 shortcuts (four rows) are shown in the collapsed surface. Rows not needed are not filled with blank tiles. New entries append to the native ordered list, at its end. They are not sorted alphabetically.
- Above 20, an up-chevron expands to the available homepage height. The expanded panel scrolls vertically; a down-chevron collapses it.
- Long-press enters editing and starts a local drag. Dropping onto another tile changes its position. Dragging near the scroll edges scrolls the expanded list. Drag cancellation does not reorder anything.
- Editing shows a small top-right remove cross and ±1.2-degree wiggle. System-disabled animations suppress the wiggle. Only visible tiles animate; hidden/background surfaces stop animation and Back interception. Done or Back exits editing; Back collapses an expanded panel next.
- Tapping a tile while editing offers full-sized Move earlier, Move later and Remove actions, including a non-drag accessibility path. The compact cross is 32dp; the dialog provides the full-sized equivalent without covering the whole draggable icon.
- Add accepts http/https URLs. Existing cached favicon data is loaded through Chromium's LargeIconBridge; a letter is used while unavailable. No custom third-party favicon lookup endpoint is introduced.
- A distinct `Add to Sandium home` menu action saves the current non-private http/https page. Existing Android launcher `Add to Home screen` remains unchanged.
- Existing Hide top sites preference is respected. The old oversized tiles card is hidden, but background and stats remain.

## Data and compatibility

This is a new native presentation of Chromium's **existing mobile profile custom-link store**, not an independent SharedPreferences/database implementation. Existing custom links, title, URL and native order remain. Native duplicate checks, supervised URL filtering and profile separation remain. Incognito has no new surface/save action. No sync policy is changed.

Mobile custom-link capacity is 200, a bounded limit. The desktop capacity is unchanged. The desktop shortcut-redesign feature cannot override this mobile limit. The old hidden Brave tile consumer is bounded to 15 returned entries to protect its layout/metrics assumptions; the new direct bridge receives all custom links. Pinned `MostVisitedSites::ImposeCustomLinks` explicitly retains custom links beyond its most-visited count. No UMA capacity constant is increased.

## Composition

`.circleci/scripts/apply-sandium-home-shortcuts.py` runs after the native theme/menu overlays. It registers one new Java source and strings, adds the native homepage child, inserts the menu model/handler, bounds the legacy consumer and changes the mobile-only native capacity. Every transformation has an exact anchor and is idempotent. A read-only verification pass detects source/resource drift. Full checkpoint/APK-first flow, #1166 component removals and #1169 navigation changes are untouched.

## Verification and remaining gates

Executed locally:

```
python .circleci/scripts/test-sandium-home-shortcuts.py ../brave-core-audit ../home-input/source/chrome_custom_links_manager_factory.cc
python -m py_compile .circleci/scripts/apply-sandium-home-shortcuts.py
```

The source test applies to pinned source copies, verifies idempotence and drift rejection, and checks resource/lifecycle/URL/drag contracts. These are **not an Android compile or instrumentation test**. No Android SDK/device is available in this worktree. Independent source review findings were addressed: bounded legacy observers, native capacity flag override, nullable field, drag completion once, URL-based drop target resolution, accessible alternatives, single-dialog guard, lifecycle cleanup, hide preference, and background animation/Back safety.

Required before acceptance: actual Full compile; first launch and upgrade with existing shortcuts; counts 0/1/5/20/21/200; add duplicate/invalid URL; private-tab action absence; reorder across rows and expanded scrolling; canceled/outside drop; delete last item; orientation and small-height/large-font screens; multiple NTPs and background/foreground; Hide top sites; TalkBack/keyboard and system animation-disabled; Back while editing/expanded; app restart persistence; no regressions to menu, stats, navigation or Android launcher action.

Visually inspect on the user's device. Source checks do not establish correct runtime geometry, pixel fidelity, absence of jank, or that the previous navigation flash has been fixed.

## Follow-up capacity, sync and launcher audit

Pinned Chromium files reviewed: `custom_links_store.cc`, `custom_links_manager_impl.cc`, `most_visited_sites.cc`, `metrics.cc`, and `chrome_custom_links_manager_factory.cc` at `d331de35ca8ab1358c7a17e4bd41627d55eaef51`.

- Mobile links use `kCustomLinksListMobile`; desktop links use `kCustomLinksList`. Both are existing `SYNCABLE_PREF` lists. This feature neither enables sync nor creates a new sharing destination. Users with existing preference sync may receive/order/edit the same mobile list on other devices.
- The native persistence format remains URL/title/isMostVisited dictionaries in an ordered list. No migration, deletion or list truncation is introduced. Native retrieval loads all stored valid entries. Lower-capacity clients may display fewer entries; source inspection does not establish their complete UI behavior or conflict handling.
- Concurrent edits on different devices retain existing whole-list preference-sync semantics. They are not independent per-item conflict-free operations. Live two-device sync has not been exercised.
- The mobile UI displays up to the native 200 limit. A previously synced/future-client list with more than 200 entries remains persisted, but only the first 200 are displayed until enough entries are removed or a larger-cap client is used. Add refuses at **or above** capacity (`>=`), without truncating or writing the oversized list. This corrects upstream's equality-only guard for the expanded list.
- `RecordNumberOfCustomTilesOnFirstNtp` uses a sparse histogram; 200 does not exceed a fixed enumeration range. The new UI does not call old tile-impression methods. The legacy hidden Java consumer remains capped at 15; its full device behavior still needs validation.
- The new menu resource/action is `sandium_add_home_shortcut`, and its label explicitly says Sandium home. Its handler only calls native `addCustomLink`; there is no `ShortcutManager`, launcher-install intent, pinned-shortcut request, or modification to the existing Android `Add to Home screen` item.

Additional executable check:

```
python .circleci/scripts/test-sandium-home-capacity.py ../home-input/source/custom_links_manager_impl.cc
```

This compiles the exact patched `AddLinkTo` function body in a C++17 host harness. Cases 0, 1, 199, 200, 201 and 250 confirm append order, refusal without truncation/write when full or overfull, and duplicate/invalid/uninitialized rejection. A preloaded oversized snapshot models an inbound sync state for this function only. **It is not a real sync transport/conflict test or Chromium build.**

Remaining sync acceptance matrix: two regular-profile devices; 21+ links and restart; simultaneous reorder/delete; old-client round trip; 201-entry imported snapshot; incognito isolation; deleting/clearing browser data; no launcher icon created by Sandium-home action and ordinary launcher action still works.


## Frozen three-state visual reference

Compared against the approved normal / expanded / edit image (`libfile_8e52d56d07488191b4d87da267cf43f1`). Normal state has no full-width command row or Add button competing with shortcuts; the distinct page-menu action adds a current site. An empty grid still offers Add. The chevron sits centered **below** the grid in a subtle sand-gold circular backing, with a 48dp accessible target. It appears only above 20 entries. The edit-only Done control is top-right, leaving the grid's bottom position stable. Tiles use compact 76dp rows and 44dp rounded icon surfaces. The expanded panel covers the stats area up to a safe top inset and uses a persistent gold scrollbar. Edit delete badges are small gold circles; native drag shadow has a gold outline and targets have dashed gold outlines. Reduced-motion and background lifecycle guards remain.

The reference's example websites/logos are illustrative; the implementation never seeds those destinations or replaces real favicons with promotional logos. The sample New badge/curved arrow are explanatory artwork, not permanent controls. Actual URL order is still append-to-end and user-draggable. Exact device geometry, wallpaper contrast and the mockup-to-runtime match still require an APK/device visual pass.


Integration update: the Nov 15 final palette supersedes gold in the frozen geometry. Shortcut accents continue to resolve the shared native colorAccent, with light-blue #6E8EB5 fallback; background fallback is #080808. Geometry and interactions remain frozen.


## November 15 numbered layout revision

The reference numbers put **20 at upper-left** and **1 at lower-right**.
Both add entry points now use native indexed insertion at position zero in
a single persisted mutation. The existing relative order, user drag edits and native
sync storage are preserved; there is no list reversal or migration. There is no intermediate append/reorder state to lose during shutdown.

Collapsed layout reserves four rows of five slots. The first item uses the
upper-left slot, with invisible non-interactive column placeholders keeping
its width consistent. The rounded, translucent dark group covers populated
rows only; unused reserved rows are transparent. More than twenty entries
shows the expand arrow. Expanded mode shows at most five rows (less if the
available viewport requires it) and scrolls to remaining items, with the
existing visible scrollbar and drag-edge scrolling. Empty state retains Add.
Labels are white against this dark surface even with a light app theme.

Homepage Privacy Stats visibility is disabled at both NTP assignment points;
Shields, counter collection and other Stats functionality are not disabled.

Validation: pinned upstream/removal composition, idempotence and drift tests;
numbered ordering and viewport arithmetic models; existing native capacity
harness. These are not Android rendering or device gesture tests. Device QA
must cover 1/5/6/20/21/25/26 items, narrow/landscape/font-scaled windows,
expansion, reorder, delete and sync changes. No CI build was started here.


### Frosted icon backing
Reference `155600.jpg` uses consistent rounded-square icon surfaces. All shortcut
icons retain 44dp outer bounds with a 12dp corner radius, a subtle static
translucent gray diagonal gradient and faint border. Favicons fit within a32dp
content square (6dp padding), preserving aspect ratio and original colors;
letter fallback remains visible until a real favicon arrives. No bitmap blur,
recoloring, wallpaper sampling or additional network fetch is introduced.
The backing is decorative; the existing full tile remains the accessible,
editable and draggable target. This is a frosted visual approximation, not a
live backdrop-blur effect. Small/transparent source favicons can still have
different optical weight; source content is not cropped or stretched to fake
identical visual silhouettes. Device visual confirmation remains required.


### Close/restart persistence audit
Java indexed insertion passes position0 through MostVisitedSitesBridge JNI to
MostVisitedSites::AddCustomLinkTo and CustomLinksManagerImpl::AddLinkTo.
Add, delete and drag reorder all call StoreLinks. CustomLinksStore writes the
ordered list to the profile's mobile custom-links preference, not this View's
memory. A newly created manager retrieves that list in stored order; the
homepage observer copies CUSTOM_LINKS in order without sorting/reversing.
Closing/detaching the page destroys bridges, not profile preferences.

Tests execute the exact patched native AddLinkTo body in a host harness,
including26 sequential front insertions, one save per insertion and recreation
from the saved list. Source audit verifies the actual pref serialization and
retrieval paths. This is not an Android process-restart/disk-flush test. Normal
close/reopen should retain order through Chromium profile preferences; abrupt
power loss before Chromium flushes pending pref writes is not guaranteed.
App-data clearing/uninstall and synchronized changes are distinct cases.


## November 16 bottom-anchored shortcut revision (supersedes earlier reserved rows)

The circled screenshot anchor is below the former empty Add card, near the
bottom toolbar. The populated grid now grows upward from a stable low baseline
(16dp outer gap + 48dp reserved footer; footer is transparent except for the
expand button when needed). There is no four-row transparent spacer below
the populated grid. Empty lists render no Add card, panel or footer. Add to
Sandium home remains available in the page menu.

The persisted newest-first list is unchanged. The partial row is at the top:
1 gives [1]; 3 gives [3,2,1]; 6 gives [6] above [5,4,3,2,1]. New entries push
earlier entries right within the growing row, and create new rows above full
rows. Columns remain equal width with non-accessible empty placeholders.
Manual reorder uses the same native list indices and does not trigger a migration.
The collapsed view retains the existing latest 20 limit; expanded mode exposes
all saved entries in the existing scrollable viewport.

Validation: pinned patch application/idempotence/drift contracts and layout
arithmetic regressions. No Android build, device pixel/gesture test, or CI run
was performed for this revision. Confirm exact baseline on the device, especially
landscape, insets, expanded scrolling and font scaling.


### November 16 transparent group and site-name defaults
The group background is now absent even when populated. Existing individual
frosted icon squares remain, with 2dp subtle shadows; labels have a small dark
shadow. New page-menu additions save a short site name from Chromium's native
public-suffix-aware domain lookup (including private registries): Facebook for
m.facebook.com, Bhaskar for www.bhaskar.com, and Example for www.example.co.uk.
IP addresses, localhost/intranet hosts and canonical ASCII IDNs are not
misleadingly reduced to a numeric prefix or Unicode lookalike.

Explicit nonempty names from the add form and all existing saved names remain
unchanged. The native store has no auto-title/custom-title provenance field,
so existing verbose page titles cannot safely be distinguished from intentional
user names. There is no destructive title migration or new preference database.
New default labels persist through the same native custom-link insertion.

Only source-contract/geometry checks have run here; no runtime PSL, process
restart, shadow rendering or TalkBack tests. Existing rename/custom names remain
authoritative when delivered by the native store. No new rename UI is introduced.

### Rename existing shortcuts
Supersedes the previous statement that no rename UI is introduced. Enter shortcut
editing by long-press, then tap a tile to open Rename / Move earlier / Move later /
Remove. Rename provides a focused, labeled single-line field prefilled with the
current name, Save and Cancel. Empty/Unicode-space-only names are rejected.
The dialog remains open on a failed save. Cancel never calls a write method.
Save validates the link still exists and calls native assignCustomLink with
identical key and destination URLs; no delete/re-add or reorder is performed.
Success is announced with a toast. Native updates store the title in the existing
profile custom-link preferences, which supply it when the browser reopens.

Executed test-sandium-home-rename.py verifies official-source blob hashes and
compiles the exact pinned UpdateLink body in a C++17 host harness. It checks
URL/order preservation, one save, reconstructed stored title and refusal for
missing/invalid targets. Dialog accessibility/Save/Cancel guards are source
contracts. Real Android keyboard, TalkBack, process-restart and disk-flush tests
are still required; this is not a claim of device validation.
