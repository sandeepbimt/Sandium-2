# Native bottom toolbar review draft

Status: **source-contract tested only; not compiled or device-tested; not wired into CI**.
Base is UI-only #1144 tree (local 507d647, published e16ba155). Chromium pin
`d331de35ca8ab1358c7a17e4bd41627d55eaef51`; Brave pin
`44a84b1f89d9a35287289d6a3d493e362f5a5123`.

## Latest requested layout

Forward | native address/search + existing glowing Sandium Shields | + | native tab count | horizontal-lines menu.

The latest user correction supersedes Add-to-Home and direct-Settings toolbar icons.
The existing menu remains the path to Settings, Install and Create shortcut; this overlay
neither removes nor remaps those actions. The logo, animation and Shields handler are unchanged.

## Implementation

- One-time native address-position migration to bottom. Uses existing position controller,
  not a floating duplicate toolbar or manually reparented omnibox. Native tablet/rotation/
  keyboard safeguards still apply. Subsequent user changes of the native position preference
  remain possible; it is not forcibly rewritten on every startup.
- Reuses native phone start-slot geometry for Forward; dispatches `ToolbarTabController.forward`.
  Clears Home long-press behavior and labels it Forward. Native meta-click callback is also replaced, so mouse clicks cannot retain Home. Disabled state follows navigation/tab observer events; observer is removed on destruction.
- Native omnibox class and all editing/autocomplete/clipboard behavior untouched.
  No clipboard reads added. Native focus expansion reserves full editing space.
- New-tab dispatch through existing activity action controller, preserving incognito mode.
- Existing tab-switcher coordinator/counter and normal menu tap retained.
- Three horizontal-line vector replaces menu glyph. New + and forward vectors registered
  explicitly in the pinned GN resource target. Minimum new-button target 48dp.
- Paint-only capsule extension includes existing Shields row without moving native text bounds.
- Removes adaptive optional extra phone button to keep the requested fixed row; underlying
  actions remain in the app menu. Android system Back is unchanged.
- Computes all transformations before writing; unexpected pins/anchors fail closed.

## Checks performed

`python .circleci/scripts/test-sandium-bottom-toolbar.py --upstream-fixtures /tmp/sandium-toolbar-src --core ../brave-core-audit`

Exact pinned fetched Chromium sources and local pinned Brave source: all transformations
and repeat application passed. Resource XML parsed. Checks confirm native omnibox class,
new-tab/incognito actions, retained Shields handler and tab/menu IDs, fixed order, no clipboard
API introduced, and fail-closed missing-Brave-include behavior. Python syntax check passed.
These checks do NOT prove Java compilation or Android runtime behavior.

## Review fixes included

- Migration remains pending before native prefs exist, preventing stale LocalState TOP from undoing it.
  Tablet preference migration is excluded. Marker follows native setting.
- Home native click callback and has-space state explicitly updated, not only normal touch listener.
- Forward state is observer-driven, not changed while drawing; disabled image alpha does not replace
  View alpha used by focus animations.
- Shields capsule uses an explicit wrapper ID. Non-Shields optional Brave phone toolbar containers
  retain native lifecycle but have zero size/no accessibility descendants; no feature policies change.
- `AndroidBottomBar` is merged into disabled features before native initialization so a separate
  experimental bar cannot coexist. Other existing disabled-feature entries are preserved.

## Integration/review gates

1. Home slot has a native Home coordinator. Its callbacks, visibility, click lifecycle and
   accessibility/context menu must be reviewed against the Forward repurposing; no stale
   Home action should remain after recreation, tab switch, policy update or focus change.
2. Shields wrapper is explicitly identified. Verify the retained Shields segment background blends
   with the expanded capsule. Review both native toolbar-animation feature variants, RTL, NTP animation,
   edit-focus transition and large text. The extension changes paint only.
3. Existing Sandium top-underlap experiment only allows TOP browser controls. A bottom toolbar
   therefore currently falls back to existing status-bar behavior. Do not claim simultaneous
   new bottom toolbar and fade effect without coordinating that eligibility change.
4. Confirm AndroidBottomBar disable is effective on upgrade, including any pre-native cached
   feature value. Confirm Brave legacy bottom controls remain gone.
5. Verify phone width 320/360/412dp, landscape, Android 14/15/16, keyboard and gesture/3-button
   navigation. Native fallback for unsupported layouts may use top placement, never duplicate it.
6. Real Android compile and smoke tests required: first install, upgrade, Back/Forward,
   disabled Forward, long press (no old Home popup), regular/incognito +, count and switcher,
   menu/Settings/Install/shortcut, Shields animation/control popup, full URL copy/paste/select-all,
   clear/go/autocomplete, rotation and process restart.
7. Edge menu integration remains separate. This overlay does not change menu dispatch.
8. No CI wiring, fingerprint changes, push or build made. Integrator must run this after Brave
   patches/UI overlays and add it to product manifest/step inputs only after review. This draft
   must not be reported as a completed APK change.

## Restored-tree CI post-apply checks

After overlay application, run (no pristine fixtures or network required):

```
python3 .circleci/scripts/test-sandium-bottom-toolbar.py --src "$SRC" --core "$CORE"
```

This inspects actual applied Java/XML/GN resources for native controls, migration ordering,
observer lifecycle, retained Shields action, incognito dispatch, single-row IDs/order and
AndroidBottomBar conflict handling. It is still a source-contract check, not a compile test.
