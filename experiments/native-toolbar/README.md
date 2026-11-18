# RawS native toolbar appearance prototype (not activated)

Baseline: RawS #1396 remote e7e782067daef429073e54c2bd8fbb91da7c8439,
local tree-equivalent2bfdcc2, tree13ed86b7767839afbd62dbed3642ce956a7adaf0.
Chromium158.0.8127.42 exact52bdd21723d5db0c9ab11716d38feac74828cf84.

Explicit adapter changes paint only: a neutral dark resting capsule lightens by
up to8 RGB levels (e.g.#212121→#292929), continuously weighted by native
focus expansion, darkness and neutrality, retaining native alpha; dark phone toolbar loading line uses off-white
#E8E6DF with transparent track. Light themes retain native contrast; incognito,
focused capsule and NTP retain native colors. No heights, padding, hit targets,
control positions, visibility, gesture/scroll offsets, viewport insets, lifecycle,
URL/security formatting or compositor ownership are replaced.

Native page-info/edit/suggestions, optional action, tabs and menu controls remain
Chromium-owned. This is NOT the full Sandium toolbar port: no fabricated Shields,
new forward/home semantics, whole-width unified capsule, menu replacement or
transparent page-underlay claim. Those need separate source-backed integration.
The phone opts into a persistent palette applied after both native theme-update
exits; internal theme refresh retains the same palette. Tablet remains native.
Device checks are required before promoting this experimental adapter.

No pipeline hook is installed. Preflight/apply require explicit invocation:
`python3 experiments/native-toolbar/adapter.py --source /path/to/src [--apply]`.
Exact preimages/postimages are validated before writing; unknown changes fail.
Retain pristine upstream files for rollback. Never apply in a live compiling tree.
Integration must add reviewed feature ownership/cache identity and run tests only
after the #1396 restore archive is certified. No build is triggered here.

## Licensing and evidence
Fixtures are copied from the exact official chromium/chromium revision; their
BSD-style headers are intact and upstream LICENSE is included. SHA256 manifest
covers each. No Brave MPL source, assets or Shields code is copied. The adapter
is newly authored; distribution must retain Chromium/third-party notices and
complete Chromium licensing workflow. This is not legal certification.

Three host tests validate source reversibility (all native code apart from the
paint additions byte-identical), strict preflight/replay and Java paint branches
compiled with explicitly limited API doubles. No Android build/API-link/device
smoothness/animation/performance certification. Check focus+IME, longURL+RTL,
private tabs, loading cancellation/tab switches and back with hidden address bar
on device before promotion.

## Exact 158 native control capability audit

- `AdaptiveToolbarFeatures.getDefaultButtonVariant`: ordinary phone default is
  native NEW_TAB; tablet/bottom-bar mode uses SHARE. User/segmentation choices
  and feature eligibility still apply, so this is not a promise of always-visible
  New tab. Do not override saved settings or force visibility to imitate Sandium.
- `AdaptiveToolbarButtonController.get`: native provider owns canShow/enabled,
  width eligibility, click wrapper and long-press customization. Retained intact.
- `ToolbarTabController.forward()`: actual native navigation action exists.
  It can be used by native menu actions without hijacking the Home view. A new
  always-visible forward slot needs explicit layout/accessibility/focus work;
  this adapter does not claim that port is complete.
- Existing toolbar XML retains native page info/omnibox, home/back eligibility,
  adaptive action, tabs and menu. Native owners remain the only handlers.
- No uBO engine is installed by this change; no Shields icon/action is fabricated.

Consequently this candidate reuses existing native controls rather than adding
parallel controls. The old Sandium overlay forces visibility/positions and
changes back-layout variants; that implementation is intentionally NOT imported.
