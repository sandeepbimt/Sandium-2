# Sandium paged menu: implementation review checkpoint

Status: **draft, not wired into the build pipeline, not published, not Android/device-validated**.

## Implementation

Original Android Java presenter, not Microsoft source. Current pinned Chromium/Brave
menu generation remains the action/policy authority. The presenter wraps the existing
PopupWindow content and keeps the original list/adapter for specialized native controls.
Tablet (smallest width >=600dp) retains the native menu.

- Inset charcoal phone popup; stable Bookmarks/History/Downloads/Settings library row.
- Paged four-column grid (two columns at font scale >1.3), eight editable actions/page.
- All Menu includes actions hidden from quick pages, plus native-specialized controls.
- + editor, draft/Done/Cancel, hide/re-add, drag reorder, page drop controls, explicit
  non-drag move earlier/later/previous page/next page commands, reset.
- Exit is **ordinary movable/removable/re-addable**, never pinned. Native confirmation
  stays intact. Dispatch no longer requires a current tab for Exit.
- Stable resource-name keys, legacy visibility migration, preservation of temporarily
  unavailable keys, no numeric resource-ID persistence.
- Product exclusions remain enforced before editor visibility. Tablet visibility
  behavior is unchanged. The phone's legacy Customize row is replaced by +.
- Footer actions use live native footer button snapshots and performClick dispatch;
  model actions retain original AppMenuClickHandler, compound controls preserve both
  primary and secondary actions. Enabled state is rechecked before dispatch.
- Live model property observers and footer loading notification update the presenter.
  Observers are detached with the popup. Back unwinds edit/all/native panels before closing.

## Integration

`apply-sandium-paged-menu.py SRC --repo REPO` validates pinned Brave/Chromium revisions,
validates all text anchors before writing, copies new sources, and registers public/internal
GN sources. It must run **after** `apply-sandium-ui-prune.py`. No CI steps or product
manifest were changed yet. Toolbar files are not modified.

## Evidence

- Source transformation + reapplication byte-for-byte idempotency test passed against
  pinned Brave audit and pinned downloaded Chromium files.
- SandiumMenuState compiled under Java17 using ECJ and its test executable passed,
  including 1,000 randomized invariants, Exit move across pages/hide/re-add/restart/reset,
  cancellation isolation, conditional-action placement, and accessibility-style moves.
- This is **not** proof of Android compilation or correct on-device rendering.

## Remaining review/validation gates

1. Real Chromium Android compilation and GN dependency checks.
2. Device test: cross-page drag after view re-render, font scaling, RTL swipes,
   TalkBack/keyboard focus, landscape/cutout dimensions, repeated open/close and back.
3. Conditional/private/no-tab/action completeness against the working #1144 browser.
4. Specialized hierarchical/custom rows use a native-controls panel, so these can require
   an extra tap: passwords/autofill parent, save/share parent, More tools, Help parent,
   update and unknown custom summary rows. Common Private Tab and compound Desktop
   controls remain direct. Review this intentional fallback before claiming exact parity.
5. New UI strings are externalized into registered Android resources; English defaults supplied. Translation coverage and resource compilation need validation.
6. A missing native icon currently uses a text initial. Review any such cases visually;
   no logo is redrawn or substituted. Fixed library row keys need on-device verification.
7. Reset resets available actions and retains known unavailable IDs; their restored
   order after reset needs product review. It does not erase hidden features or policies.
8. Legacy customization exposed elsewhere in Settings must be checked for preference
   divergence; the old phone menu row itself is removed.

Do not claim a successful APK or exact Edge behavior from the local checks above.

## Follow-up reviewer fixes

- Reset confirmation checks the exact draft instance, avoiding a callback after Cancel/Back.
- Fixed library tiles recursively disable descendants during editing.
- Narrow documented SharedPreferences checker suppression covers the isolated versioned UI store.
- Live refresh restores scroll offset, stable action/control keyboard focus and TalkBack focus.
- Native hierarchy is unwound using its existing handleBackPress API before re-entering root controls.
- Editor/description strings moved into registered Android resources; resource reference checks pass.
- State and source/idempotency tests rerun successfully after changes.

Still not integrated/built. Specialized-row extra-tap fallback remains a reviewed behavior deviation,
and live-focus/hierarchy/drag behavior remains unverified on Android hardware.

## Integration contract

After applying on the pinned real source tree, CI can run this read-only check without
pristine local fixtures:

```
python3 .circleci/scripts/apply-sandium-paged-menu.py "$SRC" --repo "$ROOT" --verify-only
```

Normal apply also runs this contract. It verifies both source pins, transformed hooks,
byte-exact copied Java/resource files, unique GN registrations and string references.
A negative drift test confirms that changed copied Java is rejected. It does not compile
Java or validate device behavior.

Palette constants have been removed. Menu/editor use shared `schemes_surface_container`,
`schemes_on_surface`, `schemes_on_surface_variant`, `schemes_outline_variant` resources,
aligned with the theme worker's day/night settings and popup tokens.

## Resource-closure and hierarchical dispatch follow-up

The appmenu internal resource closure does not include Brave's `schemes_*` resources.
Use registered local `sandium_menu_*` day/night colors with exactly the theme palette:
light #F3F3F3/#202020/#616161/#BDBDBD; dark #212121/#FAFAFA/#BDBDBD/#454545.
This is a resource-boundary implementation detail, not a separate visual theme.

Hierarchical actions are being improved to invoke their existing native controller listener
once after mounting and locating the actual attached native row. The controller must confirm
drill-down mode; model/enabled state is re-resolved and callbacks are cleared before dispatch.
Failure to locate a verified anchor leaves usable native controls instead of guessing.
This follows the existing submenu provider/back stack and does not flatten submenu actions.
Runtime layout and one-tap behavior remain unverified until Android testing.

Hierarchical auto-activation is bounded by a 500ms deadline, at most three layout attempts,
and cancellation on touch/keyboard input, navigation or detach. Both model and real anchor
must remain enabled. Unknown custom/Update/managed controls are not generically activated;
they retain the native fallback until individually audited. Therefore this is a reduction in
extra taps for verified hierarchy, not a claim of universal exact Edge parity.

## Native icon presentation contract

Grid icons now reuse `AppMenuItemViewBinder.bindStandardItem(..., ICON)` with a
normalized icon-only ALL_KEYS snapshot. This retains the existing native default tint,
explicit ICON_COLOR_RES, ICON_NO_TINT for branded artwork and ICON_SHOW_BADGE logic
without adding resource dependencies or changing action models. Drawable level is
preserved for Reload/Stop. Lazy ICON_SUPPLIER callbacks are requested once per model/
supplier, write the original ICON property, and trigger the existing live refresh.
Unavailable drawables keep the placeholder until ready; no badge rendering is attempted
on a null drawable. Source assertions cover this wiring, not visual/device correctness.
