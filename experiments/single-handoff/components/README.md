# Incremental native handoff components (not wired into the browser)

`NativePageHandoffLeaseOwner` is the resource-ownership primitive for a prospective
browser-owned native-page lease. It is compiled directly by the host regression
suite. It currently is NOT copied into Chromium by `apply.py`, included in GN, or
called by TabImpl/CompositorViewHolder. The integrated holder uses NativePageHandoffOffer directly; this prototype remains unused.

The component provides opaque acquisition tokens, exactly-once resource cleanup,
thread confinement, stale callback rejection, same-resource disposal protection,
and reentrancy-safe supersession/shutdown. Spent tokens clear page and cleanup
references before invoking external cleanup, so stale callbacks cannot retain
the native view tree through an ended token. Pending acquisitions reserve their
resource identity during cleanup to prevent contradictory ownership on reentry. Acquisition transfers ownership ONLY
when it returns a non-null token. On rejection or exception, the caller remains
responsible for its unacquired resource. Cleanup callbacks must operate only on
their explicit resource, not mutable global current-tab state.

It does not establish document/surface identity or presentation readiness.
`PRESENTED` is a reason supplied by a future validated integration, not evidence
created by the component. It does not retain renderer screenshots, delay commits,
change URL/security state, disable input, manage accessibility or change layout.
Those integrations and real Android tests remain outstanding. All EndReason
values require explicit wiring; an enum is not automatic lifecycle coverage.

Tests compile this exact Java source with warnings as errors and execute stale
callback, normal release, every revocation reason, duplicate cleanup, reentrant
replacement, empty-state invalidation, same-object cleanup, callback exception,
thread violation and permanent shutdown cases. They validate only this ownership
primitive, not navigation performance or visual correctness.
