# Sandium Android News removal candidate

Pinned Brave core: `44a84b1f89d9a35287289d6a3d493e362f5a5123`.
Apply after current UI overlays with `python3 apply.py --core <brave-core>`.
Mandatory GN argument: `enable_brave_news=false`.

The patch removes News Java source membership, JNI input and Java/C++ bridge methods,
News controller/models, settings route and ordering, menu dispatch, NTP News adapter
items and request/analytics/preference callbacks, exclusive Android layout resources,
and the unconditional native renderer RSS reader dependency and instantiation.
Native browser News implementations are already guarded by `enable_brave_news`.

Shared NTP adapter remains with stats, top sites and image-credit items; wallpaper,
Shields and normal media are untouched. Profile preferences and user data are not
cleared. Upstream source, license notices, string catalogues and harmless shared
Mojo definitions can remain in checkout; this is compiled-implementation removal,
not a claim that every News string has been scrubbed from every generated resource.

`test.py` uses the exact original pin from `/tmp/popup-brave-core` to test application,
idempotence, source/JNI exclusion and composition with the existing Sandium wallpaper
sponsored-only guard. It is not an Android compile, GN dependency dump, APK inspection,
or device smoke test. All those remain required before claiming release completion.
The operation applicator stages all files before writing and rejects conflicting source drift.
`remove-news.patch` is a reference diff only, not the runtime application path.
`test-composed.py --other-features <features-directory>` verifies Playlist then Billing
then News and byte-identical whole-chain replay.

Integration: renderer source and renderer client edits are News-only; coordinate with
AI and Playlist workers editing these files. Activity and settings hunks also compose
with disjoint removals. Apply entire staged cluster on a disposable post-overlay tree
and run GN generation/Java compilation plus first-launch/NTP/settings/menu tests.
