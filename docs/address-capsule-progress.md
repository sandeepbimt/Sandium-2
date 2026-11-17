# Address capsule loading progress

User reference: `libfile_214f736bb6008191854add2bbe05d18f`, 17 November 2026.
The blue thin loading line is replaced on the phone toolbar by a full-height,
22%-opacity green (`#46C878`) fill inside the existing address capsule.
The fraction follows native visible progress, including native completion/fade
and error/cancel reset. No separate timer or percentage model is added.

Implementation:
- Existing rounded drawable owns the fill behind URL/icons, preserving its
  insets, radius, focus geometry and RTL direction.
- ToolbarProgressBar's existing observers and alpha changes notify the capsule;
  start/finish/smoothing/accessibility logic is unchanged.
- Suppress corresponding thin Android, shimmer and compositor paint only while
  the phone capsule listener owns presentation. Tablet/custom toolbar remains native.
- Add progress and fade alpha to the native phone capture token; invisible state
  normalizes progress to zero. Native capture suppression/readiness stays intact.
- Tab switcher and detach clear capsule visibility; destruction unbinds listener.
- Canonical reset inventories and source composition/readback include all files.

Validation is source-level plus a compiled exact capture-token harness, not a
native Android build or device verification. Full reset/replay composition was
attempted but this workspace lacks older pinned Chromium appmenu/base-toolbar
fixtures needed by the repository-wide standalone composition command. The new
six transforms have pinned fixtures and focused idempotence/owner-composition tests.

Runtime limitations needing device verification:
- While native capture is blocked, the compositor can retain its previous bitmap
  until Chromium permits another capture; no gate bypass was introduced.
- Whole-toolbar bitmap updates may cost more than the original separate progress
  layer, especially during animated progress. Frame pacing is not yet measured.
- The intentionally subtle fill itself has low nontext contrast, especially in
  light theme; URL text contrast is tested above 4.5:1 over both light and dark fills.
- Test slow loads, redirects, cancel/error, quick repeated loads, tab/private
  changes, top/bottom placement, scroll/Back, focus/IME, and rotation on device.

No APK build or CI was launched for this candidate.
