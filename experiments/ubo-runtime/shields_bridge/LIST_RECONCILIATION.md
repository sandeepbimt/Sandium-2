# Native list selections → uBlock Origin

Source contract (pinned Brave 44a84b1 and uBO 1.76.4):

- Sandium uses its original-URL subscription preferences, not the hidden Brave
  component catalog. Readiness requires its completed bootstrap migration.
  An empty selection after migration is valid and must not reseed deleted lists.
- Subscription preferences are keyed by subscription URL with an `enabled`
  field; title/homepage are not source identities.
- Snapshot `lists` includes ready, revision and entries `{id,url,enabled,kind}`.
  Native ACK includes the exact revision in addition to generation/user rules.
- uBO selection contains native enabled source lists and user-filters only.
  Existing uBO defaults are NOT asserted equivalent to Brave defaults.
- Exact source URL matches use an existing uBO stock asset; otherwise import the
  original HTTP(S) URL. No title matching, UUID guesses, proxy substitution or
  URL scheme equivalence. Duplicate sources load once.
- Pinned `saveUserSettings()` does not return a persistence promise, so imported
  lists/externalLists use the existing vAPI storage interface with readback.
  `saveSelectedFilterLists()` does return its storage promise and is awaited.
- Pinned `loadFilterLists()` can resolve despite missing/empty fetches. Each
  enabled compiled source is checked before custom-rule reconciler reload and
  native ACK; unavailable sources reject rather than silently drop controls.

Boundaries: source validation proves a usable compiled payload, not equivalent
filter semantics or blocking outcome. Unsupported rules may still be ignored by
uBO. Bootstrap not ready is NOT an empty selection: startup must use its
bounded fallback and show the actual engine, never ACK unknown defaults. Native
subscription and migration preference changes trigger a fresh generation. No additional network service,
remote telemetry, title-derived ID mapping or private-profile enablement.

Tests exercise mapping, removal, duplicate native identity rejection, invalid
source, download failure and stale generation. Android native compile, actual
bootstrap readiness, subscription fetch and rule enable/disable device tests remain
required. This source helper is not proof of runtime list parity.

On a live setting change, native invalidates the generation ACK immediately;
new navigations wait for reconciliation. Existing documents may continue using
previous uBO rules while sources are acquired. The real uBO loadFilterLists then
suspends/reset/reloads its engine and unsuspends. This is not instantaneous rule
replacement for already-rendered pages; disabling a list does not resurrect DOM
that an earlier cosmetic rule removed. Reload is needed for that visual outcome.
A failed import/reload never ACKs the new generation. Timeout/failure handling is
owned by the native coordinator rather than hidden success in this adapter.

## Sandium product composition, not upstream defaults

The phone overlay `apply-sandium-filter-subscriptions.py` marks
`SANDIUM_FILTER_SUBSCRIPTIONS_ONLY` and suppresses the upstream component-list
UI. `apply-sandium-filter-bootstrap.py` seeds the 30 original URL subscriptions
and sets `kSandiumDefaultFilterListsMigrated`; its seeded-URL history preserves
user deletions. The production bridge therefore requires this verified mode and
bootstrap completion and mirrors actual subscriptions, not hidden Brave catalog
lists. No component catalog arrival is required by this Sandium product.

Offline comparison with the official 1.76.4 `assets/assets.json` matches 29 of the
30 configured subscription source URLs exactly to stock assets. The configured
annoyances-others.txt source is an external import. Two cookie stock aliases share
one exact source URL; one is selected, not both. Stock registration does not imply
a local bundled payload: optional lists can still require first-run network.
