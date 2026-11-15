# Sandium fluidity audit, 15 November 2026

Scope: consolidated source 319398c plus menu feedback f53f2a3. This is a source audit, not an Android frame-time measurement, APK test or claim of ColorOS equivalence.

## Verified source coverage
- Menu attachment owns a 100ms alpha entrance; native popup exit is 80ms. No delayed clicks or custom dismiss timers. Detach restores alpha and cancels animation.
- Menu directory/editor transitions use 120ms alpha; paging retains outgoing content during a 180ms decelerating horizontal transition. Old content is disabled and hidden from accessibility. Generation checks reject stale callbacks. Drag switches do not start page animation.
- Settings uses native transaction/activity-scoped 100ms entrance and 80ms exit resources, replacing horizontal axis transitions rather than adding a second animation. Reduced-motion is read for new transitions. Existing recorded back-stack animation resources can outlive a later system preference change.
- Welcome content has a short guarded 120ms fade with cancellation/reset on destruction. Native switch animation remains owned by Android.
- Address bar, native URL editing, keyboard following and scrolling retain Chromium/Android ownership. Adding independent translations or delayed geometry updates here would risk the URL-layout crash and keyboard discontinuity previously fixed.
- Home editing wiggles only shown tiles, checks animator settings and stops on detach/window visibility changes. Static frosty icon backing avoids live-blur cost.

## Concrete change
Custom menu TextView actions, grid tiles and page-indicator targets previously had no pressed or keyboard-focus surface. They now have bounded native ripple feedback without scaling, moving, delaying or intercepting gestures. Disabled state is transparent; keyboard focus stays visible. Reduced-motion and low-end devices use static state feedback selected when the control is created.

## Still not established
- No measured missed-frame rate, first-frame popup latency or touch-to-display latency. Source tests do not establish fluidity.
- No on-device rapid open/dismiss/reopen, repeated page reversal, drag crossing, keyboard show/hide, orientation, large font, TalkBack or system-animation-toggle validation.
- Full menu content reconstruction on model refresh may remain a performance cost. Do not replace it with a partially bound diff without proving icon/state/accessibility updates.
- Home expansion/reorder reconstructs its content. No universal continuous-layout animation is promised.
- Welcome restart currently uses a cosmetic 1000ms progress animator then 280ms fade, separate from normal entrance. This remains an audit finding: restart/readiness/lifecycle behavior needs a dedicated reviewed change, rather than silently treating it as measured loading progress.
- Compositor/website frame delivery, web-page scrolling and OS keyboard scheduling are not controlled by UI fades. Slow frames cannot be solved just by extending animation durations.
- Runtime changes to reduced-motion while an existing control/transition is alive need device verification.

## Device acceptance gates
1. Record menu open/close, directory/editor and rapid page reversals. No blank first frame, stale clickable outgoing item, clipped content or delayed action.
2. Type, select text, paste and dismiss keyboard repeatedly, including keyboard already visible. URL, suggestions and selection controls must remain attached to the intended geometry.
3. Reorder menu between pages and home shortcuts, exit/restart, verify positions and no ghost drag view.
4. Check Settings forward/back rapidly, including nested screens; no doubled slide/fade.
5. Check native button/switch feedback in dark/light, large text, TalkBack and reduced-motion modes.
6. Capture frame timing on the target device with a release-equivalent APK. Compare median and tail frame times, first-frame latency and interruption behavior against the previous APK; do not accept longer animation as evidence of faster rendering.

## Local checks
Six existing motion source contracts and ten menu source tests (including two new feedback contracts) passed. The standalone paged-menu composition runner requires audit and Chromium fixture paths; it was not claimed as an Android execution test. No CI run or publication was started.
