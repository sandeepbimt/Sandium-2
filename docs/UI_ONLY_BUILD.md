# UI-and-fixes APK, separate from the removal experiment

Owner-approved on 14 November 2026. This branch prioritizes a usable APK with the
requested UI and fixes, without the thirteen-component compile-exclusion work.

## Product source

Baseline: `104df3fefd98f22123296d05a2e6540518eb0b6e`, the pre-removal UI integration
commit. Existing Sandium product source, source preparation, vanilla-component
contract, UI overlays24–29, and normal APK validation remain identical to that
baseline. Their hashes are recorded in `.circleci/ui-only-product.json` and checked
before source preparation. This retains the thirty-list/filter bootstrap and
readiness fixes, native adblock resource/race fixes, charcoal/pale-green setup UI,
status-bar trial with compatibility fallback, Balanced S tracer, branding and
grouped native Shields popup. These are source inclusions, not a claim of current
APK or device acceptance.

The thirteen-group removal overlay is absent. The baseline's earlier existing
UI visibility/default preferences remain; this is not a clean unmodified Brave
build and does not restore every optional upstream feature to enabled UI status.
No Origin entitlement, payment gate or paid-feature access is modified.

## Pipeline and state isolation

Only Full mode. Copy the current reviewed incremental Full infrastructure,
including sixteen-layer verification, sparse restore, APK-first upload, bounded
35-minute compile slice within the one-hour job, and verified maintenance/readback
with the peak-local-disk fix. Keep exact upstream pins and ordinary signature,
package, branding, archive and source-revision validation. There is no stripped-APK
acceptance claim or stripped-APK-only gate on this product.

Branch: `experiment/sandium-ui-only`.
Checkpoint namespace: `sandium-exp-single-v1-bridge-ui1088`.
Every job checks both values before any checkpoint restore/publication. The
removal branch/namespace remains unchanged. Seed this new lineage from the exact
original verified compressed base using `allow_seed_import=true` once. Never
import a removal head or delta chain here. Later runs use `allow_seed_import=false`.
Original restored APKs are rejected when their source revision differs, then
normal source/GN regeneration decides what compilation can be reused.

Only one actual build should run after the removal workflow has settled. Retain
the common project serial group. The removal branch's existing daily maintenance
schedule remains untouched. This branch carries maintenance capability but does
not by itself create a native CircleCI schedule; register a UI-lineage schedule
only if ongoing use of this lineage requires it, and verify its actual execution.

## Required acceptance

Review/test this adapted pipeline and product-isolation contract before publishing.
A successful local test is not an APK. Verify actual CI restoration, compile,
archive/signature/package/branding gates, artifact upload and incremental receipt.
Compare the produced UI with the frozen welcome/popup requirements, and disclose
any untested device behavior. Keep the removal experiment's evidence and lessons
on its own branch so that work can resume without losing the fixes.
