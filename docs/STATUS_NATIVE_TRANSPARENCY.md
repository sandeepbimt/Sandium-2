# Native status-surface investigation (16 November 2026)

## Evidence and bounded fix

The supplied Settings and Homepage-settings screenshots show an elevated dark
status strip above a black shared header. The NTP screenshot instead shows a
black status strip above the wallpaper. These are different owners.

`BraveSettingsActivity.initializeSystemBarColors` retains its base activity's
status colour while Sandium's shared header/root is changed to the settings
surface. Match that owner's colour to `sandiumSettingsBackground()`. This keeps
light mode and dynamic-colour opt-in, and delegates icon contrast to the existing
system-bar colour helper. No new OS calls, touch interceptors, window-insets
listeners, web-underlap eligibility, padding, or browser-control offsets change.
The E2E helper paints the backing when the platform status window is transparent;
this is not a direct opaque Window status bar override.

This fixes the Settings/sub-settings colour mismatch only. It is NOT the complete
requested gradual native transparency and MUST NOT be presented as such.

## Still required before claiming full completion

* NTP wallpaper needs to extend behind the status area without translating the
  interactive native page. A transparent status colour alone would expose an
  unrelated root/window colour instead of wallpaper.
* Native settings and other native browser screens need an explicitly owned
  background-under-inset surface and gradual protection overlay. Preserve their
  safe content inset (header title/back button must not rise under system icons).
* Do not reuse ordinary-web underlap eligibility for native pages. That owner is
  Android-16-gated and tied to the scroll-away status spacer; enabling it for
  native pages would introduce the exact geometry instability being investigated.
* Check Android 15 and 16, light/dark/dynamic colours, portrait/landscape, cutouts,
  keyboard, NTP -> Settings -> sub-setting -> back, and wallpaper change with
  frame capture before declaring no flash. No APK/device result is claimed here.

Focused validation: native theme fixture tests cover original pinned source,
repeat application, migration from previous patched source, and existing inset
listeners untouched. No native Java compile or rendered gradient proof yet.
