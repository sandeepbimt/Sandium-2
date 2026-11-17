# User-filter preflight (uBlock Origin 1.76.4)

`sandium-user-filters.js` is a helper, not an installed bridge by itself. Its
caller must import it before setting `µb.readyToFilter` or starting network
observers. After native snapshot reconciliation resolves `applied: true`, the
caller can finish tab initialization/start observers and acknowledge native
readiness with the SAME generation. A later settings event must immediately
invalidate the helper and native eligibility, fetch a new snapshot and apply it.
A stale result, rejected storage/reload or disposed bridge must never ACK.

Native `customFilters` is authoritative for this isolated experiment. Empty
text removes previous native custom rules. This does not merge extension UI
edits: do not expose independent uBO user-filter editing without implementing a
native write-through path. No third-party lists or other selected lists are
removed. This helper must not enable runtime cutover or suppress Brave itself.

Pinned APIs inspected in official release 1.76.4 `js/storage.js`:
- `loadUserFilters()` -> asset object with `content`.
- `saveUserFilters(content)` trims, invalidates compiled user filters and returns
  the asset write promise; we read back content before proceeding.
- `saveSelectedFilterLists(keys)` updates in-memory keys and returns storage
  promise. `applyFilterListSelection()` does NOT return that promise in this
  version, hence it is deliberately not used here.
- `loadFilterLists()` resolves after engines freeze, filtering-behavior
  notification and selfie invalidation. Re-run at startup even when persisted
  text matches, rather than assuming an earlier selfie is current.

These calls do not prove every Brave custom-rule syntax is supported by uBO.
Unknown rules may be discarded by upstream parsing; controlled network block,
exception and cosmetic integration checks are still required. Likewise no
successful promise establishes Android runtime behavior without actual APK
execution. On reload rejection caller must fail startup, not claim a recovered
engine (upstream can retain a rejected loading promise).

Test: `node experiments/ubo-runtime/shields_bridge/test_user_filters.mjs`.
Tests use a fake storage/engine and verify ordering, authoritative deletion,
selection persistence, first/same-content reload, generation invalidation,
stale reply rejection, readback failure and disposal. They are not APK tests.
