# Exact-source, partial offline startup sources

This integration snapshot reduces first-install network work without changing
Sandium's active selection or replacing any list. **Coverage is 28 of 30**:
8 exact stock bodies already present in the verified uBO 1.76.4 package plus
20 additional original-source bodies (16,012,469 plaintext bytes). The remaining
2 retain their original network fetch path and can still cause the existing
bounded startup fallback. This is not a fully offline startup guarantee.

Missing original snapshots after bounded download retries:
- EasyList Notifications and Other Annoyances

`sources.lock.json` enumerates all 30 original product URLs in exact order,
records the 20 vendored plaintext SHA-256 digests/sizes, and marks the unavailable
2 explicitly. The product `FILTERS` catalogue is read on every apply: catalogue
drift or corrupted payload fails before source mutation. No mutable build-time
network fetch and no altered upstream release ZIP/hash are used.

The integration adds an exact-source local fallback inside pinned upstream
`assets.get()`, **after its normal cache read** and only while
`µb.readyToFilter !== true`. It never writes a raw cache, calls `assets.put`,
changes the source registry, or changes list selection. The original
`getContentURLs()` result is copied, not mutated; only an exact original source
URL (or identical imported asset key) can match a packaged source.

Upstream's own `fetchFilterList()` loads the local body. Its existing cache-write
condition accepts external URLs only, so the injected extension-local source
cannot overwrite a concurrent fresh remote cache entry or reset a cache clock.
Existing cache content wins before this hook is reached. Remote refresh retains
all original URLs/intervals. Once startup marks `readyToFilter` true, subsequent
reconciliation, deletion/re-addition, and normal refresh never use this fallback.
This is a source fallback, not a persistent cache seed. No claim is made that
parallel upstream remote/compiled-cache operations themselves are race-free.

All current additional source bodies contain no `!#include` directives. A
future replacement with include directives is rejected until its dependencies
are separately audited/packaged. The regression test executes the pinned
upstream `fetchFilterList` implementation on an extension-local relative include
fixture; it does not substitute a homemade include flattener. No claim is made
that arbitrary future conditional/include graphs are supported by this lock.

## Ownership / integration

Apply `python3 experiments/ubo-runtime/offline_lists/apply.py --core BRAVE`
after request-policy (and Shields), before activation (which rehashes manifest/disk inventory).
Reset activation before this overlay, then reset this overlay before request-policy and Shields
and loader. If status is applied last, reset status first as usual. The
payload is staged in CI for both default-off foundations and activated candidates;
merely staging assets does not enable runtime features. The original reserved
700 resource IDs suffice; inventory overflow fails rather than silently growing.

The independent receipt restores exact preimages, rejects unowned edits and
removes only its newly owned empty asset directory. Native materialization
verifies the resulting disk-resource inventory before component registration.

## License / attribution

Every complete original filter body, including attribution and licensing
headers, is retained byte-for-byte. The lock records the original source URLs;
filter headers point to each publisher's governing license and source project.
uBO integration code remains GPL-3.0-or-later, with the uBO source/license
artifact already supplied by the parent bundle workflow. EasyList-derived
bodies retain their original license link, AdGuard bodies retain their license
link, and the phishing list retains its source/license notices.

**Dan Pollock's hosts file explicitly allows redistribution for non-commercial
uses with original URL and attribution.** Both are preserved in the source.
This experimental package is for the owner's personal testing; this snapshot
must not be represented as commercially redistributable without separate review
of that restriction and all other source licenses. Packaging these bytes does
not change their individual licenses or assert universal compatibility.

Tests: `python3 .../test_offline.py` checks lock and full loader+Shields+payload
apply/idempotence/reset/unowned-edit behavior. `node .../test_seed.mjs` checks
cold-only source selection, immutable URL arrays, absence of cache writes and
pinned local include resolution. These are source/model checks, not Android
runtime performance or filtering proof.
