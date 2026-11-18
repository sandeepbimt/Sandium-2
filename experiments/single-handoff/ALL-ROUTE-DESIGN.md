# Whole-navigation handoff: feasibility and remaining integration

Status: design beyond the bounded implemented profile. Not production wiring.

## Ownership by route

| Route | Presentation owner | Readiness / limitation |
|---|---|---|
| ordinary HTTP(S) web navigation | Chromium paint holding | bounded500ms eligible main frame; FCP or valid contentless exit; no universal blank prohibition |
| animated Back/forward to web | native BackForwardTransitionAnimator | matching destination item sequence activation; native failure/cancel policy |
| animated Back to native home | native animator + corrected native delegate | generation-scoped native layout/feed readiness; pre-draw is not physical presentation |
| ordinary web to native home | **missing holder-level adapter** | install/live layout/draw ownership needed, not a generic paint callback |
| ordinary native home to web | **missing holder-level adapter** | retain native view until target web presentation eligible; coordinate lifecycle destruction |
| native to native | **missing holder-level adapter** | incoming view staged and laid out; old view destroyed only after replacement admission |
| external intent/new tab | existing navigation and tab policy | no unrelated old-tab screenshot retention; empty initial view is legitimate |
| security/error/crash/contentless destination | native failure policy | must remain visible/accessible, cannot wait forever for nonblank pixels |

## Source constraints that dictate the design

TabImpl.showNativePage only creates its smooth delegate during animated Back.
TabImpl.hideNativePage notifies the content change and immediately destroys the
previous native page. CompositorViewHolder removes its outgoing overlay before
adding the next. A delegate-only patch therefore cannot retain an already
destroyed page for ordinary navigation.

CompositorViewHolder.addDidSwapBuffersCallback is not a general next-frame fence:
it may run immediately after the holder has drawn once. requestRender's layout
callback is not Android View presentation. Neither is an acceptable invented
'ready on screen' signal.

## Holder-level implementation direction

1. Separate selected tab content from presented content in the holder. One
   generation owns pending and presented view identities, target navigation and
   resources. URL/security remain the native browser model, not forged by this
   presentation adapter.
2. Stage a live native child at final measured geometry. Do not block the root's
   pre-draw: root blocking would also freeze browser progress and Cancel/Back.
   Evaluate a holder-owned drawing container that admits the incoming native
   child only after its layout is valid, while retaining the outgoing child.
   This is live view lifecycle ownership, not blanket screenshots.
3. Defer outgoing native-page destruction until the holder releases its lease;
   keep the old child noninteractive and excluded from accessibility while it is
   retained as a loading presentation. No clicks go to invisible destinations.
4. For native-to-web, destination-associated activation is necessary but not
   proof of physical presentation. Validate compositor availability and Android
   surface composition before removing native cover. Do not fake a frame fence
   with an unrelated swap callback.
5. Supersession/cancel/background/crash/tab switch release leases exactly once;
   no arbitrary timer extension. Existing security/error paths supersede retained
   content. Bound resource use to one outgoing and one pending live native view,
   never a growing history of retained pages.
6. Preserve BrowserControlsManager geometry and composited toolbar ownership.
   The live native staging container must consume the same final controls bounds,
   not add independent margins or translations.

This needs actual CompositorViewHolder/TabImpl integration and Android testing;
a standalone state-machine test is not proof that cross-surface handoff works.

## Immediate responsiveness

Navigation dispatch and green address-bar fill start without waiting for the
handoff. Browser Back/Cancel remain responsive. If source retention would create
misleading old-origin/new-URL presentation, native security policy wins. Maintain
native timeout/contentless behavior rather than silently making a site appear
hung until it paints something we consider interesting.

## Required acceptance before enabling

Test actual pinned compiled integration, then same-device sequences for each row
above with controls shown/hidden, rapid replacement, dark/light policy, slow and
blank documents. Prove no extra blank/color stage introduced by the adapter and
no duplicate viewport shift. Do not conflate13 passing host tests for the initial
profile with these not-yet-implemented or device-verified requirements.

## Visual contract

Tap feedback and green loading fill are immediate. The page remains geometrically
stable; successful handoff is one restrained replacement, not chained fade-out,
color fallback, fade-in or bounce. The bounded candidate removes the optional
ordinary blur chain and preserves the existing native-home100ms fade with
exactly-once ownership. The future ordinary holder path should not add another
fade over that owner. Host lifecycle tests assert admission/completion ownership;
actual motion appearance requires device rendering, not a fabricated mock video.

## Pinned history test comparison

Independently fetched d331de35
`content/browser/navigation_transitions/back_forward_transition_animation_manager_android_browsertest.cc`
(SHA256 `9c55bb7b17bd9529dd850cb8f4e0d619dc408964e7411da23bcb5366a5ceda6c`).
`TestLayerTransformsDuringCrossFade` intercepts destination renderer metadata,
asserts `kWaitingForNewRendererToDraw`, then permits first-frame activation and
checks a single crossfade. This preserves the DESTINATION history screenshot,
not arbitrary outgoing-origin content over a future destination. Production
`kDismissScreenshotAfter` is four seconds; errors and cross-origin redirects
skip the activation wait. Do not turn this test into an unlimited retention rule.

Read Chromium's security policy before any broader overlay proposal:
https://chromium.googlesource.com/chromium/src/+/main/docs/security/overlay-policy.md
It documents cross-origin full-page overlay risks including mismatched security
identity, active hidden prompts/media/input, and warns that merely blocking input
or adding a timeout does not resolve the complete threat model.

WebKit reference (architecture only, no code copied):
https://github.com/WebKit/WebKit/blob/main/Source/WebKit/UIProcess/ViewGestureController.cpp
Use its per-gesture/page identity and exactly-once completion discipline, not its
platform-specific overlay implementation or watchdog constants. The concrete
Sandium target is stale async TabImpl callbacks mutating a replacement view.
