# uBlock Annoyances: 30th default subscription

Base: Sandium #1075 (`952b614ef375ec524954c27997d0e491936d21cb`). No Origin removal changes.

## Official source and choice

uBO's official assets catalogue lists `uBlock filters – Annoyances` at:
https://ublockorigin.github.io/uAssets/filters/annoyances.txt

At inspection on 13 November 2026 that file contained only the include directive
`!#include annoyances-others.txt`. Sandium's native subscription downloader does
not expand list includes. Therefore the 30th entry uses the official direct leaf:
https://ublockorigin.github.io/uAssets/filters/annoyances-others.txt

Visible name: **uBlock filters – Annoyances**. The leaf's own upstream title is
“uBlock filters – Other Annoyances”. Its inspected Last modified header was
12 November 2026 17:27:24 UTC, with a seven-day expiry. This is an updating
subscription, not a pinned or bundled copy. Existing cookie-notice subscription
is unchanged. Official catalogue reference:
https://github.com/gorhill/uBlock/blob/master/assets/assets.json

## Upgrade behavior

- Append one new unique default URL; existing 29 entries/order unchanged.
- Existing native seeding adds it enabled only if it has not previously been
  explicitly deleted. Existing subscription settings and manual lists remain.
- Remove the obsolete migration that deleted historical Annoyances URLs on
  every startup. No subscription data is deleted by this change.
- “30” means 30 configured defaults, not a forced cap/count on the user's
  actual list collection. Manual or historical subscriptions can make it larger.
- Keep native update scheduling and last-known-good cache behavior unchanged.

## Licensing and verification limits

The list header points to the uAssets GPLv3 licence:
https://github.com/uBlockOrigin/uAssets/blob/master/LICENSE

This patch subscribes directly to upstream; it does not copy or relabel the
list contents. Preserve source attribution. If future work bundles or merges
list bytes into a distributed artifact, include the applicable licence/notices
and corresponding-source obligations for that distribution.

Offline subscription/idempotence and bootstrap structural tests pass. Actual
Android upgrade, list fetch, parser/scriptlet compatibility and device runtime
remain to be verified in the combined build. Adding this list is not itself a
claim to fix the Hindu failure or to support every uBO rule.

## Restored-checkpoint source migration

The native manager is not reset by the existing shared-source reset. Explicitly
migrate only its known generated 29-entry catalogue and obsolete purge block
before idempotence checks. Unknown source drift still fails closed. This edits
build source, not the user's stored preferences. A retained exact-pin generated
29-list manager fixture verifies surgical migration and repeat application.
Also exercised the complete old bootstrap followed by the new bootstrap twice
against a materialization of the exact pinned upstream files: passed.

## #1079 composition failure and correction

The first checkpoint fixture omitted the later homepage-warmup overlay. That
left a test gap: the real checkpoint contains `MaybeTriggerSandiumHomepageWarmup()`
inside the bootstrap-owned Ensure method, so strict body verification failed
although the 29-to-30 catalogue migration succeeded. The correction accepts only
that exact known composed variant, preserving its warmup call and rejecting
unknown method drift. The retained fixture now includes all actual homepage
manager transformations. Regression executes the native-manager branches of
`apply()` twice, rather than only testing the migration helper. A separate local
integration exercise applied old subscriptions, old bootstrap and full homepage
overlays to pinned source, then applied the new bootstrap twice: passed. Real
CircleCI/build/device verification remains required.
