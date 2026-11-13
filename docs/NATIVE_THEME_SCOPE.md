# Sandium native charcoal/pale-green theme

Approved direction (13 Nov 2026): darker charcoal, near-white hint of green, consistent active buttons/toggles. This patch is separate from the no-logo welcome redesign and status-bar transition.

## Implementation

`apply-sandium-native-theme.py BRAVE_ROOT` rewrites existing Brave Android resource overlays and the dynamic-color default. Apply after other source/color overlays, before GN/Android resource packaging. No added resource filenames or BUILD.gn entries are necessary.

- Default dark native surface: `#1B1F21`; elevated card: `#292E31`.
- Default dark primary/active controls: `#E6F4E8`; on-accent foreground: `#18231B`.
- Common Chromium `baseline_primary_80` drives standard dark controls. Brave `schemes_primary`, button and interactive-text tokens match it.
- Normal/off controls retain neutral states and existing disabled alpha. Security/error colors and private-window identity tokens are untouched.
- Light mode remains light and uses `#365B40` green foreground/controls to retain contrast against white. Pale-on-white is intentionally avoided.
- The persisted theme preference is never rewritten. An explicitly enabled Android wallpaper/dynamic-color preference still wins. Unset dynamic-color preference now selects the fixed Sandium palette rather than the remote Brave default; its Java unit-test expectation is updated accordingly.
- Website content, content darkening, third-party identities, services and renderer behavior are untouched.

## Verification

Six Python tests cover palette consistency, XML/idempotence, duplicate rejection, protected scope, explicit preference preservation, and contrast. Dark on-accent and main text combinations meet WCAG normal-text 4.5:1. Applied and reapplied to exact pinned Brave source, with identical second output. Native Android compilation, native Java test and device rendering have not run in this isolated task.

## Limits / device checklist

This covers native baseline/themed controls, not an assertion that every hard-coded custom control or WebUI color was found. Inspect settings, permissions, Shields, dialogs, tabs, downloads, normal/incognito, light/dark, disabled states and font scaling in the new APK. Explicit dynamic colors can produce different colors by user choice. Check contrast and state distinction with the real Android widget styles.

Preserve the welcome patch's native-readiness logic. This palette patch does not fix readiness or alter filter activation.
