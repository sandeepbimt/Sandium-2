# Menu glyph and disclosure provenance

- Frozen Sandium presenter: `d3e82450867d3be2c5724244c4077b0457814d55`.
- Its Brave Core: `44a84b1f89d9a35287289d6a3d493e362f5a5123`. Frozen
  `BraveTabbedAppMenuPropertiesDelegate` selects `ic_outside` for Exit,
  `ic_shred_data` for Shred data, and explicitly substitutes the blue
  Bookmarks/History/Downloads/Settings glyphs and Recent Tabs icon.
- Frozen Sandium `apply-sandium-home-shortcuts.py` specifies
  `ic_baseline_add_24` for its distinct browser-home pin action. Copy of
  donor vector bytes is unchanged. This is not Chromium's Android launcher
  install action, which remains its own real command.
- Nala asset mapping: exact Brave `android/nala/icons.gni`, included as
  evidence. Brave Core dependencies pin Brave Leo
  `c5f9c8f78f3df5b767a83ad67babd8b29323266a`. The generator reads source
  `icons/*.svg` and emits standard 24dp Android vectors. This isolated
  materializer preserves exact path data and fill rule; the monochrome fill
  is mapped to the local Sandium menu palette and actual Chromium ViewBinder
  continues tinting paint. No unsupported SVG feature is silently approximated.
- Desktop Site and Site Controls use the unchanged exact donor Chromium
  `d331de35ca8ab1358c7a17e4bd41627d55eaef51` vectors
  `components/browser_ui/styles/android/java/res/drawable/ic_desktop_windows.xml`
  and `components/omnibox/browser/android/java/res/drawable/ic_settings_tune_24dp.xml`.
- The native bookmark's CHECKED state chooses the exact donor empty/filled
  ribbon geometry. The native live Reload/Stop drawable remains owned by
  Chromium and is not replaced by a static icon when it exists. Disabled
  unavailable Reload has the exact donor Refresh path. Exact live Reload/Stop
  rendering is a remaining parity limitation.
- Chromium shipped Ask Gemini only when `GlicEnabling.isEnabledForProfile`
  returned true. Brave Core at the donor pin unconditionally disables that real
  path (outside test override). This slice removes the stock row from both
  RawS page-menu producers and independently excludes its stable resource ID
  from the custom catalog. There is no placeholder, lane, or edit add-back for
  it. No actual AI engine policy, setting, or data was changed.
- SVG-derived files use MPL-2.0 conservatively per the pinned repository
  LICENSE.md included under glyph-inputs; PNGs were not imported. Original
  upstream Chromium XML notices are retained. The exact donor SVG/XML source
  bytes, original pins and Git blob hashes accompany the materializer. Preserve
  notices and source disclosure when integrating, rather than redistributing
  only generated XML without corresponding sources.

The corresponding pinned source geometry and repository license are retained
in this directory; renderer resources are sealed by RawS's exact production
recipe. The sources are review/disclosure files only and are not added to the
APK build graph. The source names and verified Git blob hashes are in
`geometry-source.json`.
