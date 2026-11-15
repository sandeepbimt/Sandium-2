# Dark Pages implementation and release gates

## Current user scope

The owner's latest revision is **one Oppo-inspired webpage palette, global defaults,
per-site Dark Pages On / Off / Follow global in Shields, and a separate manual
element color corrector**. Separate automatic logo/header, image and CAPTCHA
correction controls were withdrawn. They must not appear as inert settings.
Image/challenge safeguards remain defaults; no CAPTCHA is solved or bypassed.

This worktree contains a Java/profile/UI implementation draft, **not an enabled
or device-validated feature**. Its transformer is intentionally not wired into
the Full pipeline. The native renderer and manual element corrector are separate
integration dependencies. Do not claim a functioning complete feature from host
tests or expose controls without their consumers.

Base: reviewed #1177 tree `0621e027`; Brave
`44a84b1f89d9a35287289d6a3d493e362f5a5123`; Chromium
`d331de35ca8ab1358c7a17e4bd41627d55eaef51`. Eventual consolidated integration must
also include reviewed #1177 hermetic fixture repair `4b88b71` and its current
approved successors; never run the old shallow-checkout test dependency again.

## Implemented Java layer

- One `DARK_PAGE` setting. Site values are Follow global / On / Off. Reset deletes
  the override rather than saving a snapshot of the current default.
- Exact canonical HTTP(S) origins from GURL (scheme, host, nondefault port), not
  page-provided strings or registrable-domain guesses. No credentials, paths,
  queries or fragments are persisted. Different subdomains remain distinct.
- Non-syncable profile preference `sandium.dark_pages.policy_v1`, with registered
  default empty string (effective dark-page default On). JSON contains `global`
  and `sites` objects. Unknown/corrupt settings fall back to defaults. Serialized
  writes have a 256 KiB limit; the previous state remains intact on write failure.
- Normal profile snapshots load once, avoiding repeated JSON parsing in native
  preference resolution. Writes copy the snapshot and publish only after a
  successful persistent save.
- Private site overrides are memory-only and do not import normal-profile site
  history. They inherit global defaults. Profile destruction removes private
  policies and cached snapshots. Global writes from private profiles are rejected.
- Availability checks cover private profiles and their original profile. Stale
  dialogs cannot mutate a replacement profile or another origin. Rejected writes
  produce an error and restore/dismiss the control rather than show unsaved state.
- Global Settings and Shield site dialogs are drafted with explicit reload.
  The Shield entry is outside ad-block-master-dependent content. Welcome and the
  existing Appearance master switch use this same setting; saved onboarding
  values are restored without overwriting them.

## Native contract

`WebContentsThemeClient.sandiumDarkPageFlags(WebContents, GURL documentUrl)`
returns bit 0 for enabled; all other bits are reserved and currently zero.
Ineligible/unavailable documents return zero. It does **not** query the visible
or pending address. The native caller must supply a trusted document-bound URL.

The original Chromium FORCE feature immediately returns true and bypasses site
exceptions. Java's old native callbacks are deliberately unchanged: the renderer
integration must override that result for eligible HTTP(S) documents, including
explicit Off, after Chromium computes native defaults. It must clear custom flags
when the client/document is absent and reject error/opaque/internal documents.

The renderer prototype is separately owned. Its exact source analysis finds
post-navigation preference recomputation inside `DidFinishNavigation` after
observers. That proves a post-commit hook, **not** pre-first-paint delivery. Do not
substitute the pending URL to mask this gap. A screenshot/device/navigation test
must determine visible handoff; strict first-paint guarantees need a separate
commit-time document-policy path.

## Tests and reproducibility

- `tests/run-policy-tests.sh`: 23 actual Java model assertions.
- `tests/run-profile-tests.sh`: 27 profile-adapter and 7 actual UI-callback
  assertions, with Android/Chromium native APIs stubbed.
- `.circleci/scripts/test-sandium-dark-pages.py`: 6 pinned transformation tests,
  source hash verification, idempotence, explicit-document JNI signature, scoped
  UI controls and deliberate absence from build wiring.

Run with JDK 21, for example `JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64`.
Profile tests additionally require `JSON_JAVA_JAR` pointing to JSON-java 20240303
from Maven Central. The verified jar SHA256 is
`3cf6cd6892e32e2b4c1c39e0f52f5248a2f5b37646fdfbb79a66b46b618414ed`.
The tests do not download dependencies. Android's platform JSON implementation
and native persistence still require real Android verification.

The upstream fixtures retain their license headers. `sha256.json` pins exact
fixture bytes. The welcome fixture is Sandium-owned from the reviewed base,
not an unmodified upstream Chromium file.

## Remaining integration gates

1. Independently review matching renderer candidate and explicit document origin
   binding, stale resets, exact JNI signature and actual palette consumers.
2. Integrate manual element correction only with working native document/session,
   exact-origin profile persistence, reversible preview/cancel, anti-retarget
   safeguards and private-session isolation. Do not reuse adblock storage.
3. Register all modified/new files in reset inventories; replay against clean and
   accepted checkpoint composition, update source contracts, and include #1177's
   hermetic test repair before any consolidated Full run.
4. Compile actual Android/Blink/generated JNI/Mojo/Settings. Host stubs and source
   tests are not a substitute. Inspect the resulting APK before delivery.
5. Device validation: normal/private persistence, tab changes, pending/cancelled
   navigation, commit/back/BFCache, error/internal pages, already-dark websites,
   photos/video/SVG/canvas/challenges, text/selection/form contrast, manual header
   correction and page reload. No universal website compatibility claim.
