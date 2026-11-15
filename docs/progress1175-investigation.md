# Sandium #1175 duplicate loading lines

Inspected exact published base 51feb9da1fe4f14492c10b1b365fc16d54673b63 and screenshot libfile_72b24a31ef2481918b12a2108186a583. Isolated worktree sandium-progress1175 (fix/progress1175) remains unchanged. No build/publication performed.

Observed: active white partial progress over grey track above toolbar, and separate full-width grey line at toolbar boundary approximately one toolbar height lower. Screenshot does not prove both animate or that lower line disappears at completion.

Pinned Chromium d331de35ca8ab1358c7a17e4bd41627d55eaef51 code:
- ToolbarManager initializes ToolbarProgressBar + ToolbarProgressBarAnimatingView. LoadProgressCoordinator drives native state, with polite accessibility live region.
- ToolbarProgressBarLayer translates all compositor drawing rectangles together. Bottom path uses stacker heights, progress container height, and optional hairline height.
- BottomControlsStacker height-from-layer-to-bottom is inclusive. ToolbarPositionController progress layer has zero height. Formula alone does not establish duplicate toolbar-height subtraction.
- C++ ToolbarLayer::UpdateProgressBar uses foreground Y for static background. Those layers cannot independently account for this separation.
- ToolbarControlContainer has a distinct ToolbarHairlineView. TopToolbarOverlayMediator handles native/compositor hairline visibility, including AlwaysDrawCompositedToolbarHairline flag.
- ClipDrawableProgressBar tracks desired Android and composited visibility separately, influenced by animated-progress and APB flags. Runtime flag state unavailable.
- Bottom compositor positioning combines viewport height and toolbar offset; native/compositor coordinate mismatch remains a hypothesis requiring measurement.
- Sandium bottom/unified/focus overlays create no extra progress widget. Forward blur paints content surface and fallback, not progress.
- Brave legacy bottom controls explicitly disable when native address toolbar bottom-anchored.

Conclusion: plausible native/compositor visibility/geometry mismatch, but lower line ownership (progress background vs hairline) is NOT proven. Do not hide an arbitrary layer or claim a fix. No source changes or tests justified yet.

Next diagnostic: during load capture numeric native progress/container and hairline screen rectangles, native progress/animating-view visibility+alpha, toolbar position, APB flags, compositor DrawingInfo rectangles, viewport height and bottom offset. No URLs/content or unbounded per-frame logs. Compare before/during/completed/interrupted load. After identifying ownership, keep one indicator at content-facing toolbar edge and preserve loading accessibility/cancellation. Test top/bottom, scrolling, keyboard, rotation, incognito, cancellation on device. Source tests alone cannot validate visual correction.

## Recording follow-up
Recording libfile_cd1411e53f488191a8e13ca1cabcfb4b is 6.034 seconds, 720x1570. Examined contact sheet and 10fps crops over 2.7–4.2 seconds. Before load: neither line. Around 2.8 seconds the lower full gray line appears; around 2.9 seconds the upper active line appears and grows through roughly 5–35% while lower remains full gray. Around 3.9 seconds both disappear as destination becomes visible. This proves load linkage, not two independent page loads; the lower line remains non-animated. It excludes a permanently displayed webpage divider but still does not distinguish native background from compositor hairline appearing during toolbar capture.

Diagnostic candidate in isolated worktree: apply-sandium-progress-diagnostics.py, NOT yet wired to pipeline. Only TraceEvent-enabled numeric geometry/state, max24 changed snapshots per trace period, no URLs/text/page data. No rendering changes. Four tests passed. Independent review approved the corrected diagnostic; no Android compilation/device verification.

Apply explicitly after pinned source checkout only if diagnostics are desired:
`python3 .circleci/scripts/apply-sandium-progress-diagnostics.py --src "$SRC"`
Then use `--verify-only` to check presence. No CI step is added automatically. This is a measurement candidate, not a correction. Record a short local trace around the load and inspect `SandiumProgressGeometry`. Native screen locations versus screenshot line positions distinguish the layers; reported native visibility may be overridden, hence desired visibility and alpha-presence are included separately.
