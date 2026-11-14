# Sandium neutral theme review

Based on UI-only #1144. No removals, engine changes, build/pipeline changes or logo edits.

- Native dark surfaces: black background, #212121 containers, #303030 elevated controls, neutral fine outlines. Primary action #F5F5F5 with #171717 content; primary text #FAFAFA, secondary #BDBDBD.
- Light theme retains light surfaces and uses #333333 action text instead of illegible near-white accents. Existing explicit dynamic-color preference wins.
- Welcome keeps approved layout, copy, spacing, card radii, readiness logic and green success state. Checked switch uses light track/dark thumb; inactive and disabled states stay differentiated.
- Existing status protection is made darker at its top and fades to transparent. It remains a painted scrim, not blur. Existing Android 16 portrait/phone/gesture-navigation and safe restoration guards remain. Actual native bottom-controls placement is now eligible only with zero top-control height, positive bottom-control height, zero top minimum offset and no forced visibility. Mixed/transitional top layers fail closed; ineligible device/window/page states restore the ordinary status bar. Native integration and device validation are still required before claiming the bottom-row effect works.
- Shields count green/yellow resources, Sandium logo assets and animation are untouched.

Validation: palette XML/idempotence and contrast tests; all pinned status transforms and previous-gradient checkpoint migration; UI-only source manifest. These are source checks, not Android compilation or device rendering tests. Native compilation and portrait/landscape, keyboard, light/dark, cutout and accessibility checks remain necessary. This does not assert that every inherited settings surface already consumes these tokens.

## Expanded source coverage audit

Audited pinned Brave Android `brave_colors.xml` day/night, `brave_styles.xml`, named filter layouts, bookmark/sync drawables and pinned Chromium ToolbarPhone. Expanded neutral baseline primary/secondary/tertiary and neutral/neutral-variant families used by Settings, preference controls and dialogs; neutralized explicit filter-editor, bookmark-dialog, QR/default-browser-sheet, sync-panel, toolbar text and generic bottom-sheet tokens. Added explicit day counterparts and contrast tests. Menu implementation is instructed to consume the shared `schemes_surface_container`, `schemes_on_surface`, `schemes_on_surface_variant`, `schemes_outline_variant` resources rather than unrelated literals.

Coverage limits, not evidence of complete app-wide visual equivalence:
- Existing explicitly enabled dynamic-color setting can still override native attributes. This patch does not silently erase the user's saved choice.
- ToolbarPhone derives non-NTP address background from toolbar/website color through ThemeUtils; the baseline textbox token is covered, but website tint paths are not forcibly replaced here.
- Android/system-owned permission sheets, keyboard, OS share/file selectors cannot be made identical through app tokens.
- Feature-specific Wallet/VPN/Rewards/Leo and WebUI CSS retain their own non-theme/semantic colors; this work does not indiscriminately overwrite security/error/success states or brand assets. Further source/runtime inventory is needed for full all-subscreens scope.
- Welcome currently uses its approved dark layout even in light mode; regular Settings/menu use theme-qualified light/dark resources. This is a deliberate existing behavior, not proof of a universal theme lock.

Device screenshots are still needed for Settings root, privacy/security, appearance, filters/custom filter editor, site-permission dialogs, downloads/bookmarks/history, menu pages/editor and omnibox focused/unfocused in both day/night modes. Keep status safety matrix testing separate from palette checks.


## Regular browser chrome seam

The new `apply-sandium-chrome-theme.py` transforms pinned Chromium TopUiThemeColorProvider's shared `isThemingAllowed` decision only for an Activity whose concrete class is ChromeTabbedActivity (after unwrapping a ContextWrapper). This prevents website/activity color values from tinting regular browser chrome while keeping the native default-background / branded-foreground decision together. It does not mutate Tab theme metadata or page CSS. Native pages retain their scene-layer background logic and incognito retains its native distinctive palette. Custom-tab/PWA activities are not selected. Existing explicit dynamic-color preference remains honored; enabling it intentionally selects the native dynamic app palette instead of neutral defaults, rather than leaving a checked-but-ignored switch. No additional theme picker introduced.

Source regression tests check exact pinned transform, idempotence, native color/foreground path preservation, scope and no preference/page mutation. Runtime needs contrast checks across focused/unfocused omnibox, normal/incognito, day/night, tab switching, NTP animation, custom tab/PWA, dynamic enabled/disabled. No full-screen uniformity or runtime verification is claimed. Feature WebUI and native-page-specific backgrounds remain gaps needing separate inspection.

## Enabled bottom-bar provider

Exact pinned BottomUiThemeColorProvider was inspected: its enabled-BottomBar route previously sourced background from BottomControlsStacker, whose bottom-most visible colored layer wins. The narrow regular ChromeTabbedActivity/non-incognito route now uses the provider's existing SemanticColorUtils app surface and matching default tint. It does not recolor the layer itself or send a color feedback notification into the stacker. Other activities, incognito, and disabled-BottomBar branches retain original behavior. This keeps explicit dynamic color working via the native surface attribute. Fixture tests cover both provider transformations and repeat application; device layer transitions remain unverified.
