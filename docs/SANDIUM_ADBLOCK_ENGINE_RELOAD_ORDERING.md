# Sandium native ad-block engine reload ordering

## Problem

On a fresh install, subscriptions can finish downloading and show non-zero rule counts while the active native engine still contains an older or incomplete aggregate. The Content Filters UI reads cached list text and metadata; those values do not prove which asynchronous engine build is currently active.

## Latest-build-wins protection

Pinned Brave v1.98.62 notifies the filter-provider manager independently as providers initialize or subscription files become available. Each notification starts asynchronous filter-set aggregation, resource loading, and engine creation. Those operations can finish out of order.

Sandium stamps each aggregation with a monotonically increasing generation. The generation is checked after filter aggregation, filter-set creation, and resource loading. A stale completion is discarded; only the newest requested build may publish its engine. This does not change subscription URLs, list contents, or user enable/disable choices.

## Full Mode packaged baseline

The Full Mode DAT integration supplies an additional-engine baseline only when the profile's additional DAT is missing or rejected by the native deserializer. The APK DAT is loaded through Brave's normal engine wrapper and copied to the profile cache only after successful deserialization. A valid profile DAT remains untouched.

After the packaged baseline loads, Sandium explicitly releases the additional-engine startup notification suppression. If the packaged DAT is missing or invalid, the same explicit release is used for the live subscription-provider fallback. Provider notifications can then progressively replace the bundled snapshot. The generation guard ensures older subscription aggregations cannot replace newer ones.

The default engine DAT (engine0.dat) is not modified. Brave's scriptlet and redirect resources continue to come from its separate resources provider.

## No homepage warm-up or page reload

The earlier NewTabPage-visible warm-up approach was removed. There is no homepage hook, NTP request, navigation, tab reload, or subscription toggle in this implementation. The packaged engine protects the first navigation directly; normal provider updates proceed in the background.

Do not restore a homepage warm-up hook as a way to trigger the native engine. The native provider-manager API is the intended engine-refresh mechanism.

## Regression coverage

The pinned-source patch adds:

- An out-of-order completion test that holds an older aggregate until after a newer blocking rule is active, then verifies the older completion cannot replace it.
- A default-engine startup-suppression bypass test.
- An additional-engine startup-suppression bypass test, matching the packaged DAT engine.
- Deferred-notification tests for both engines when providers are not yet initialized.

The offline patcher tests verify idempotent source transformations. The C++ tests and the generated Rust DAT still require Full Mode CI execution; their presence in source is not evidence that they have run.

## Validation

Full Mode CI must apply all overlays to the pinned Brave Core revision, compile the modified native code, run the relevant native tests where the workflow supports them, generate and round-trip-validate the adblock 0.13.3 DAT, package the uncompressed Android asset, and prove Siso remote execution and checkpoint reuse. A successful APK is not claimed until the ARM64 Release APK is ZIP-valid and installable.
