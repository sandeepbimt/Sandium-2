# Full Mode-U: Address-bar loading progress

Replace the old translucent green capsule fill with a thin off-white
(`#F4F0E8`) line along the existing capsule's straight top edge. The
line follows Chromium's existing visible progress, fade and reset state,
including RTL direction. It does not resize or relayout the address bar.
The original compositor progress paint remains suppressed only while the
phone capsule owns presentation; other toolbars retain native behavior.

Validation: the six targeted source transforms were checked for matching
anchors and idempotence against the exact Chromium 158.0.8127.42 files.
Focused tests cover toolbar composition, edge geometry, no layout request,
and a compiled capture-token harness for fade/reset/restart. This is
source-level validation, not an Android build or an on-device visual test.

Phone check: verify dark and light modes, slow load/fade, rapid cancel/reload,
RTL, Back with hidden address bar, and no stale progress or green fill.
