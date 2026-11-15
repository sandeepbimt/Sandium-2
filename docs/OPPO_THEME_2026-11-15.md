# Oppo-reference baseline, 15 November 2026

## Reference and interpretation
Two owner-provided Oppo App info screenshots have dominant flat pixels of black
`#000000`, grouped surfaces `#1A1A1A`, and enabled-switch blue `#198CFF`.
The screenshot of Sandium Setup is the old appearance, not the new palette.
JPEG compression/antialiasing is not used to infer an exact OEM design system.
The requested appearance is reproduced with native Sandium controls, not copied
Oppo assets. Sandium logo and animated Shields artwork are unchanged.

## Covered surfaces
- Shared Chromium baseline neutral/primary families and Brave native night tokens:
  Settings roots/subscreens, text, buttons, ordinary popup/dialog surfaces,
  bookmark/import/filter interfaces, toolbar and location-bar surfaces.
- Welcome's separately owned colors and existing rounded groups now match the
  shared dark baseline. The progress-fill's old gold literal is removed.
- Paged menu/editor outer surface black, rounded groups #1A1A1A, active blue.
- Homepage shortcut panel uses the same grey at 80% alpha to preserve the
  owner's requested translucent wallpaper treatment, rather than opaque black.
- Native Settings preference lists get a decoration with 16dp corner radius,
  12dp horizontal gutters and 6dp group boundaries. Contiguous siblings share
  a group; category headers are not painted. Native adapter, row widgets,
  ripple, keyboard, click handling and accessibility are unchanged. Existing
  custom row/card backgrounds are not destructively replaced, so some custom
  cards may cover the decoration. Non-preference pages keep their native layout.
- Toggle styling is a separate reviewed companion change, not this commit.

## Deliberate exceptions
Explicit dynamic-color opt-in is still respected for other controls; it can override
the baseline. Companion switch styling deliberately uses fixed #198CFF tracks
and white thumbs across modes, so a pastel dynamic primary cannot erase thumb
contrast.
Light mode keeps readable light surfaces and a darker blue foreground. Error,
security, incognito identity, success messages and webpage content are not
recolored. This is not a claim that every WebUI/custom view or Android-owned
permission dialog has the exact same pixel values or rounded grouping.

## Verification and remaining device work
Palette contrast tests cover primary/secondary text, active control colors and
light/dark pairs. Overlay is idempotent and fails closed on changed pinned seams.
Full pinned reset/replay composition was tested; native build and Android device
rendering have not been performed by this isolated task. Before acceptance check
welcome, main Settings, Privacy/Appearance/filter subpages, Shields, menu and
All menu editor, dialogs, long lists, large fonts, light/dynamic modes. Check
that grouped preference decoration remains visible beneath native row ripples
and does not collide with a custom card; do not report universal coverage until
that runtime audit is done.
