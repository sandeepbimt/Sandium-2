# Sandium navigation performance audit

Status: conservative source-side latency patch and diagnostic fixture; NOT yet benchmarked on a device.
Base: feature/sandium-page-transition-full at 32bfca61c3f2fd5be60592b745ebd37645410af0.
Review branch: feature/sandium-navigation-response-20261114.

## Architecture and findings

Sandium's pinned Brave/Chromium engine owns session history, same-document and cross-document navigation, scroll restoration, BFCache, HTTP caching, reload semantics, and error pages. A Java-side URL/scroll snapshot layer must not duplicate engine history or bypass native BFCache. The existing Sandium blur and darken overlay affects animations only, not caching.

The prior Full overlay configured optional medium hold/fade-out as 450/225 ms (675 ms total) and high as 675/300 ms (975 ms total). This patch uses medium 240/120 ms (360 ms total) and high 320/160 ms (480 ms total); low remains 200/100 and default remains disabled. These are configured visual animation durations, NOT measured page load times. The native transition may finish earlier or have its own readiness/fallback policy.

## Reproduce all six navigation paths

Run from the repo root:

    python3 -m http.server 8765 --bind 127.0.0.1 --directory tests/navigation-performance

For a USB-attached Android device, run:

    adb reverse tcp:8765 tcp:8765

Open http://localhost:8765/probe.html?page=a in Sandium and stable Chrome. On iOS Safari, use a controlled LAN host instead; do not expose the fixture publicly.

1. Initial load: record responseStart, DOMContentLoaded, load end, visible first paint, error events, and long tasks.
2. A to B: navigate with the in-page link; check for blank frames, redundant loads, or duplicate history entries.
3. Back from B to A: scroll A to marker, navigate to B, return. Record pageshow.persisted and final scrollY. True means direct BFCache restoration; false may be due to eligibility or memory, not necessarily a bug.
4. Refresh: use the Refresh button. PerformanceNavigationTiming.type should say reload, not back_forward. Honor HTTP validators and service workers rather than faking a restore.
5. History and position: repeat A-B-Back-Forward-Back after scrolling. On the stable-layout fixture, restoration should be within 8 CSS px; preserve separate entries and forward navigation.
6. Loading hiccups: throttle networking and use real offline/error cases. Look for canceled requests, renderer kills, incomplete paints, spinner stalls, console errors, and notRestoredReasons where supported.

Export probe JSON from the fixture. Entries stay in tab sessionStorage until cleared; avoid real URLs, cookies, page content or identifiers. Run >=20 warm repetitions per path on comparable devices and report median and p95 for perceived input-to-paint time, navigation timings, BFCache hit fraction, scroll mismatch, error rate and long task time. Static tests or cache hits alone do not establish a speedup.

## Implementation policy

Keep Chromium native history/BFCache and automatic scroll restoration. Do not force-enable unknown native flags; confirm exact pinned engine defaults and any BFCache blockers first. Limit speculative preconnect/prefetch to low-risk user-anticipated navigations only, subject to data/battery/memory limits, incognito isolation, and sensitive URL restrictions. Never speculatively trigger logout, payment, POST or unapproved credentialed cross-origin requests.

Do not trade away Sandium's Shields or filter readiness to improve load measurements. The repo contains ad-block filter-bootstrap, homepage warmup and asynchronous generation-race protection overlays: profile those interactions before changing them. Do not mask loading failures behind long animations.

## Build and release

Only Java startup animation parameters and Python source-overlay tests change in this patch; select FAST MODE for this incremental source change when a compatible native compiled checkpoint exists. The base feature branch itself contains native C++ transition changes: retain their compatible compiled outputs, and use FULL MODE only if native C++ or GN state is invalidated.

Protected canonical reference: commit 3c8004b, CircleCI cache job 949 (26 GB). Never modify it. Verify all shards/manifests, source pins, Siso/GN/object restoration and actual output reuse before trusting a cache hit. New branch changes do not promote the reference.

Release gates: offline overlay tests; pinned-source overlay validation; CircleCI branch-trigger verification; real Fast Mode reuse; signed ARM64 Release APK validation and installation; device BFCache/back-forward/reload/scroll tests; accessibility and privacy checks. No build or device benchmark has been executed for this review branch.

## Browser technical references

Chrome BFCache: https://web.dev/bfcache/
Chrome lifecycle: https://developer.chrome.com/docs/web-platform/page-lifecycle-api/
Chrome prefetch: https://developer.chrome.com/docs/web-platform/implementing-speculation-rules
WebKit Page Cache: https://webkit.org/blog/427/webkit-page-cache-i-the-basics/
Mozilla BFCache: https://developer.mozilla.org/en-US/docs/Glossary/bfcache
Mozilla scroll restoration: https://developer.mozilla.org/en-US/docs/Web/API/History/scrollRestoration
