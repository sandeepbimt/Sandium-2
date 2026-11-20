# RawS regular-browser document resource blocking

This source candidate adds an Android dependency and one browser-side
`kDocumentSubResource` network factory. It is not a build mode or separate
product. Nothing is enabled unless the regular browser's startup code submits
one trusted offline rules asset through the native initializer.

## Pinned integration

* Chromium `52bdd21723d5db0c9ab11716d38feac74828cf84`:
  `chrome/browser/chrome_content_browser_client.cc`,
  `ChromeContentBrowserClient::WillCreateURLLoaderFactory`, and
  `chrome/browser/BUILD.gn` :core. The link transformer verifies the exact Git
  checkout and file preimages, and needs the staged native component sources.
* Brave `bd6d26d1bced03c17a98baa86d2cd3425d543d1b`:
  the limited native filter engine and Rust/CXX bridge are taken from the staged
  vendor closure. The adapter follows the pinned Brave Standard matcher; this
  does not import Brave startup, lists, services, redirects or cosmetics.
* Browser startup may call `InitializeDocumentSubresourceRules` only with an
  audited, integrity-checked local rules asset. The initializer itself validates
  size (8 MiB limit), UTF-8/NUL constraints and engine load status, not
  distribution provenance. It loads that one list into the default collection
  and uses an empty additional collection. No production API accepts renderer
  input, command-line test rules, changes to a live engine or a remote URL.

## Bounded scope and remaining evidence

The factory considers only HTTP(S) GET/HEAD scripts, styles, images and fonts,
for a non-opaque HTTP(S) factory initiator. Unsupported/trusted/body-bearing
requests or initiator mismatch pass through unchanged. Each check is bounded
to 50 ms on the calling sequence; at most 32 engine tasks may be pending
process-wide. Tasks are admitted after startup has scheduled initialization,
and queue after it on the worker. Requests can pass during initialization,
overload or timeout; a late result cannot cancel an already forwarded request.
A factory created before startup invokes the initializer remains unchanged.
No claim of first-request readiness is made.

Only a definite on-time match cancels. Allowed loads go to the unchanged
downstream factory using the original endpoints, options and request. This
first slice **does not re-evaluate redirects**. It does not intercept
`URLLoader::FollowRedirect`, mutate CORS or other security flags, rewrite
requests, or substitute responses. There is no worker, prefetch, navigation,
WebSocket, CNAME, CSP, cosmetic, scriptlet, or full Brave parity claim.

Before release, run the actual pinned nine-case host smoke and
`RAWS_ENGINE_SMOKE_V2_PASS`, verify the Android compile/link and component
graph, and obtain device evidence from a controlled allow/block test plus
normal downstream redirects, late decisions/startup and teardown. Native
tests can call the same initializer in a disposable browser process; no
fixture is discovered through normal browsing. The supplied host checks
exercise source contracts and the C++ decision rules with boundary doubles,
not Chromium Mojo, GN, the real Rust binary, or the APK.
