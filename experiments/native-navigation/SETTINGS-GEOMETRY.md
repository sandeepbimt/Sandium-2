# Native motion with Sandium appearance preserved

Baseline Chromium: `d331de35ca8ab1358c7a17e4bd41627d55eaef51`.

`settings.plan(root)` returns two modified source texts for the navigation
profile's existing validated journal transaction. Include `settings.py` and
`settings-reversal.json` in its recipe hash. It performs no writes.

* SettingsActivity: restore the complete pinned `setFragmentAnimation` method,
  including native shared-X-axis TWEEN and PROPERTY choices. Complete-method
  reversal avoids ambiguous open/close resources that shared the same fade name.
* BraveSettingsActivity: remove Sandium activity fade overrides and custom finish
  hook, retaining the original lifecycle and existing Sandium theme/background.
  Do not restore the obsolete per-view alpha animation that preceded this fade.
* Existing packaged fade resources can remain inert. No caller references them
  after restoration; keeping them permits exact journal rollback without deleting
  resources or altering unrelated appearance.

Geometry uses `native.plan(stage, paint=False)`. This restores standard inset and
controls ownership and removes the former experiment's gradual status gradient.
The currently applied opaque status color policy remains unchanged: this request
is not a return to transparent/scroll-under status. Wallpaper outer root and
foreground, address capsule styling/height and theme are not modified here.

Tests compare restored Settings sources byte-for-byte against pinned fixtures
(with theme-only transformation for Brave Settings), verify drift fails before
writes, and verify geometry leaves current opaque-paint sources unchanged.
Full composed profile and device navigation/Settings testing remain necessary.
