# Genuine graph-only precheck

Set `run_graph_precheck=true`, `publication_reviewed=true`, and `allow_seed_import=false`, with the existing isolated experiment namespace. Use the same reviewed branch for configuration and checkout. The diagnostic workflow takes precedence over `run_experiment`, so it cannot launch the five-stage build alongside itself. It uses the same serial group.

This is not a second APK build mode. Flow remains the single APK build mode.

The precheck restores the exact accepted base plus all ordered deltas, validates pins, executes the same source preparation and UI overlay steps, then runs real pinned GN generation and the central, low-six and Leo dependency/source audits. Independent audits are aggregated after successful generation instead of stopping at the first audit violation. A failed generation never uses a stale graph.

By default it deliberately does not take the prebuild capture inventory, run remote compiler smoke tests, compile, package, export an APK, capture a new increment, save caches or publish a checkpoint head. After the graph passes it plans source-owner compile checks and verifies packaging-tool availability. Optional `precheck_compile_seconds` greater than zero performs a bounded targeted compile, capped by the remaining job deadline with shutdown/artifact reserves. The default is zero (plan only). Timeout/no-time is incomplete, never a pass. Targeted compilation is not final linking or APK proof, and its outputs are disposable and not checkpoint-published. It leaves the accepted checkpoint untouched. Diagnostic results and partial audit reports are stored as job artifacts, including on failure. PASS_GRAPH_ONLY means graph/preparation checks only, never a verified APK.

## Cost and verification limits

The current workspace only has Brave core audit sources, not the full pinned Chromium/dependency checkout. A real GN graph cannot be derived locally from those fixture snippets. The first cold CI precheck still pays for full checkpoint transfer and reconstruction (recent runs were roughly 16 minutes for reconstruction plus preparation). It avoids the separate roughly 3-minute capture baseline inventory and all subsequent compilation/checkpoint work. No fixed time or credit saving is promised before measurement.

A warm, separate diagnostic source snapshot could avoid repeated reconstruction, but is not implemented here. Saving/restoring such a snapshot has substantial storage/upload costs and requires explicit input completeness and isolation validation. Merely adding a job does not make the cold restore cheap, and a source-only cache must not omit generated GN/hook inputs by guesswork.

Passing this check cannot establish C++/Java/JNI compatibility, link success, package resources, APK absence, signature, installation, upgrade or runtime behavior. Those still require the real build and artifact/device gates. A graph precheck cannot promise to find every possible later build failure.
