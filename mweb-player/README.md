# RawS #1514: mobile YouTube player-data candidate

**Status:** tested source candidate, not a sealed release or an APK. The parent is `1bdd41e4c478459ca6b86b1717dac601e17c832b`, tree `e602433276fbe78e975347f8ac51362a848edc71`. The parent object and root tree were independently reproduced and hash-checked before editing. The local work used a sparse object repository with no remote; the candidate preserves every pre-existing root entry verbatim. No production archive, signing, triggers or build configuration changed.

## What changes

`player.js` handles direct or one-level `playerResponse` JSON parsed without a reviver; it also handles successful, nonredirected JSON `Response.json()` reads from the exact mobile player API. Only a playable (`OK`) player object with a video ID and nonempty format data or a SABR URL qualifies. Remove only its own array-valued `adPlacements`, `playerAds` and `adSlots`. No arbitrary recursion, list-supplied JS, network/response rewriting, playback seek, CSS, consent or checkout handling. No console output or collection of URLs/IDs. Disabling marks old wrappers inert, preserves subsequently installed wrappers and restores native methods where still owned. This does not reverse data already consumed by the page.

`glue.py` applies four hash-pinned edits to existing compiled Chromium owners. The browser sends a per-document site-policy boolean on a dedicated Mojo method; the renderer checks frame, document token, HTML, origin and liveness. Only constant source runs in the page world without user activation or a native bridge. This is **not** an extension. The hook is dispatched on the existing browser policy/style refresh; it is **not** guaranteed to precede page startup. This does not sanitize assignments of inline object literals, worker-side parsing, native `xhr.responseType='json'`, `resolve_url` prefetch envelopes or server-stitched ads. Seeing one of those on a handset would justify a separate change; the attached logger cannot distinguish them.

References used for behavior, not copied implementations:
- uBlockOrigin/uAssetsCDN `filters/filters.txt`: mobile `json-prune`, root and `playerResponse.*` placements/ads/slots; `filters/quick-fixes.txt`: distinct prefetch rules. These are upstream references, not an inventory of the user's installed lists.
- gorhill/uBlock `src/js/resources/json-prune.js`: JS parser proxy and separately matched response handling. This implementation is independently written and narrower.
- #1514 postimage `9e7fa353…` (`subresource_decision.cc`) and `5ad05cc0…` (`document_subresource_factory.cc`): ordinary POST and requests with bodies are forwarded without native subresource matching. Changing that boundary or blocking `googlevideo.com` is not this fix.

## Reproduce locally

Prerequisites: Git, Python 3.10+, a C++20 compiler, FFmpeg with libvpx, Python Playwright and desktop Chromium (`CHROMIUM` may specify its executable). No videos, logs, identifiers, credentials or fetched captures are stored. WebM test clips are generated into a temporary directory. The browser suite binds a synthetic origin and transport in `about:blank`, retains the real Response/JSON methods, and waits for a decoded HTMLVideoElement frame. It does not navigate to or contact YouTube. The C++ suite uses the exact postimage bytes; URL and Rust matcher dependencies are test doubles; it does not measure a list match.

```
python -B mweb-player/test_browser.py
python -B mweb-player/test_request_gate.py
python -B mweb-player/test_seal.py
```

## Production integration — explicit, offline, no CI

A checkout of the source-candidate commit alone still selects the original #1514 recipe. **Do not build it expecting the new behavior.** In a complete local clone containing the parent and candidate, use a disposable detached worktree at the candidate. The full parent objects, especially the production recipe and four postimages, are mandatory. No network fallback. The dry run performs all the transforms and checks before offering a local commit:

```
python -B mweb-player/seal.py           # print four postimages and four metadata hashes
python -B mweb-player/seal.py --commit  # create ONLY refs/heads/local/raws-1514-mweb-sealed
```

The second command writes a new **sibling** of the candidate, directly parented to #1514, with the candidate sources plus the actual sealed product files. It uses a temporary index; it never moves HEAD, overwrites an existing ref, or invokes `git push`. It preserves the old immutable postimages, full path inventory, all original Chromium preimage hashes and all unrelated manifest and proof bytes. The only metadata edits are the four `after_sha256` values, the admission's recipe digest and the two matching tool pins. Inspect the resulting tree and run the repository's own restore/feature verification before building. The complete-base dry run, native compile, signed APK, restore and device verification were **not** performed in the sparse environment. Test-seal exercises the same transformation on minimal source slices and synthetic metadata; it is not a substitute for those checks.

## Device acceptance

Compare base and sealed candidate on a monetized mobile watch visit where an ad opportunity is independently demonstrated. Capture **redacted** player key names, parser path, navigation type, whether the hook arrived before consumption and ad/content first-frame order; never save raw URLs, signed parameters, cookies or response bodies. Repeat direct cold open, search-to-watch, next-video/Back, signed-in and signed-out, Shields on/off. Confirm normal startup, seek, A/V continuity, captions, quality changes and midroll transitions. A run with no ad opportunity is inconclusive. For publisher follow-up record DOM identity, bounding box, creative/empty state, insertion time and opening frame/target; validate consent, authenticated and subscription controls separately.
