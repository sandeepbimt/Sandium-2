# Native-home handoff candidate

Pinned Chromium d331de35ca8ab1358c7a17e4bd41627d55eaef51. Original delegate retained
as full fixture; full TabImpl original compressed fixture from the same pin.
Source patch only: no Android compile, runtime jump fix, or presentation proof.

This changes **the existing animated native-home path**, not all homepage entry
routes. NtpSmoothTransitionDelegate currently accumulates animation-end listeners
across starts; cancellation/reuse can invoke prior completions again. The candidate
makes each start own its callback, animator, feed observer and generation. Teardown
removes listeners before cancel, retires ownership before invoking external code,
and drops late feed/animator/timeouts. A reentrant newer start is not overwritten.
TabImpl additionally verifies the original NativePage and WebContents identities
before notifying native content-shown; a callback cannot target a replacement page.

Feed readiness now admits the native alpha animation at an attached, laid-out,
non-layout-pending pre-draw with positive bounds. No new margin, offset, controls
state, layout request, or screenshot is introduced. setAlpha already invalidates
the native view; a valid traversal is observed rather than fabricated. If no valid
traversal occurs, the existing native fallback budget releases the operation once
without keeping a cosmetic cover indefinitely. That budget now covers feed,
layout and animation, rather than only waiting for feed. A monotonic pre-draw
check enforces expiry even if the Handler task is delayed. On cancellation or
detach, release is immediate, with page/WC ownership guard at the native callback.

The wallpaper wrapper and foreground layout stay owned by NewTabPage.updateMargins;
this patch does not assert that their capture/live coordinate contract is correct.
Controls-in-Viz and main-thread controls paths are unchanged; no flags enabled,
no Java translation attempts to follow compositor offsets. Pre-draw is not GPU
presentation. Controls can still move after admission; testing must include hidden
bar, back-cancel, native-page replacement, full-screen, orientation and slow feed.

Host tests compile the full transformed delegate with Android collaborators and
exercise readiness, repeat start, old listener/observer/timeout delivery,
reentrancy, deadline, detach and cleanup. Full original source transforms and
combined web/home journal rollback are tested. These are not Android API or
compositor runtime verification. Native metrics' fallback boolean now identifies
whole-operation deadline expiry, including absent traversal, not only feed delay.

## V2 queued UI ownership

The pinned TabImpl OTHER-stage `requestRender` callback previously looked up
`getView()` at delivery, so queued work could hide a replacement native view.
It now captures page, view, WebContents, stage and transition generation. The
same predicate protects smooth completion and the canceled-native-page `view.post`
completion. A valid current cancellation still signals content shown; stale work
cannot signal the replacement transition. OTHER/NONE notifications, all four
explicit delegate-cancel sites, current native-view detach, hide, and WC binding/
release retire generations. `isDestroyed()` also rejects callbacks after teardown.

Full TabImpl fixture was refreshed from the exact d331de35 pin fetched via Gitiles
into /tmp/pinned-handoff; the archive stores source, not generated candidate code.
Host tests compile the actual transformed stage method with collaborators and run
current/stale requestRender, view replacement, stage replacement, valid canceled
completion, WC/page replacement and destroyed-state cases. This is an asynchronous
ownership correction, not a compositor presentation fence or all-route staging.

## V3 liveness and once-only acknowledgement

WAIT has an explicit acknowledgement owner and a generation tombstone. Repeated
WAIT cannot bypass the active delegate or re-arm a completed cancellation. The
canceled-native branch posts its owned acknowledgement even when alpha was already
one, covering WAIT arriving before queued OTHER-hide work. Detach/explicit cancel/
hide may release only the still-current page/view/WC in WAIT; this is an abort
release, not evidence of a presented frame. Replacement bindings simply invalidate.

Pending ownership is cleared before the native callback. Captured old delegates
are removed from shared state before cancellation. If native acknowledgement
synchronously produces normal NONE, attachment/hide cleanup still continues; a
newer transition/page instead stops stale caller cleanup. A distinct terminal-
generation marker preserves normal notifyContentChanged without notifying a new
owner. Native callbacks may synchronously reenter: tests execute actual transformed
TabImpl stage, detach, cancellation block and hide methods, including both detach
listener orders, normal NONE, reentrant newer owners, and duplicate/late callbacks.
All nullable owner locals/parameters are explicitly annotated; host javac does not
substitute for Chromium's Android nullability/compiler checks.

Cached delegates are operation-reused objects, not operation identities. The old
caller now checks retirement ownership BEFORE invoking cancel on its captured
delegate. If acknowledgement installed a newer owner, it does not touch that
delegate again. A superseded old operation not reused is bounded by its existing
operation deadline; reused delegates retire the old operation on start/prepare.
Tests cover same-instance acknowledgement reentry as well as deadline cleanup.
