# Ordinary web handoff scope

Integration: call `web.plan(source_root)` AFTER the existing pinned native
navigation transform. Merge its planned text into the parent's reversible
transaction. Only SplitCompatApplication startup changes. No independent
transition manager, asynchronous observer or extra source set is introduced.

The optional AndroidNavigationBlurTransitionAnimation manager is disabled before
native FeatureList initialization, stripping parameterized enabled entries and
normalizing duplicate disabled entries. Unrelated feature entries are preserved.
Saved Sandium blur preferences remain inert. This is an explicit experiment
change, not a claim that enabling blur still has an effect.

Chromium's existing renderer commit deferral / surface paint holding remains the
owner. The inspected pin d331de35 LocalFrameView::WillDoPaintHoldingForFCP uses
Document::DeferredCompositorCommitIsAllowed(), an outermost-main-frame guard and
a once-per-document guard. Its native timeout and eligibility are NOT expanded.
RenderWidgetHostImpl::InitializePaintHolding already coordinates input routing.
Do not set a guessed 'PaintHolding' feature switch or force old cross-origin
pixels to persist. No global timer extension is introduced.

Removing the optional overlay eliminates its blur -> theme/white fallback ->
page sequence. It does NOT guarantee a single visual frame on every navigation:
slow renderers, native paint-holding timeout/eligibility, dark application,
redirect/error pages, BFCache, native home and predictive navigation need their
own verified behavior. Native error pages must remain visible when appropriate.

The metadata/item-sequence guard from BackForwardTransitionAnimator is a useful
reference for future surface-readiness work, not justification for installing a
second ad-hoc handoff coordinator. Native home Java content cannot be certified
by the renderer item sequence; that work is separate.

Tests: five host tests pass, including compilation and execution of the exact
Java startup block using the JDK compiler module. Cases cover absent/empty
switches, parameterized/trial entries, duplicate targets, unrelated features and
repeat invocation. Android APK compilation and device behavior remain unverified.
No build triggered.
