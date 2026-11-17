# Native-navigation status geometry profile

This module reverses all64 exact scroll-status replacements across18 source/test
files, then retains only bounded gradient painting in the native reserved status
area. No hidden spacer, synthetic CSS safe-area, root padding override, alternate
inset-controller creation or forced bottom-toolbar `consumeTopInset=false` remains.
The latter is why simply passing scroll-status `--disable` is insufficient.

`native-status-geometry.py:plan(src)` returns validated changes without writing.
The whole native-navigation experiment owns preimage capture, atomic planning,
manifest verification and on/off restoration. Paths are disjoint from Back,
ordinary transition, homepage handoff, wallpaper and capsule source changes.
Recognized overlay overlaps fail closed; unrelated edits outside exact fragments survive.
The whole-profile owner must validate admission/restoration hashes. This helper is
not a general validator of arbitrary hand-edited Chromium geometry. The known
identifier-free bottom-inset suppression is explicitly rejected.

## User-visible experiment tradeoff

Web content no longer scrolls beneath the status bar: native inset ownership
reserves it. This is required for a genuine pinned-native geometry baseline.
The dark gradient remains paint-only on backing colors for which the pinned
native contrast rule selects light foreground (3:1 white contrast); light backing
keeps native paint, avoiding black icons over a newly darkened gradient. The
source of this rule is pinned ui/android/.../ColorUtils.java. No icon policy is
changed. Wallpaper, capsule appearance and separate native-theme status colors
are not edited by this module; their actual combined appearance requires phone
verification. Native NTP handling is separately owned by the full experiment.

Five source tests prove exact native geometry restoration, paint-only exception,
repeatability, native-input support, unknown-overlap failure before writes and
preservation of unrelated changes. These are not Android compilation or runtime
navigation/paint verification.
