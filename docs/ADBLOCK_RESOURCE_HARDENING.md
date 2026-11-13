# Sandium resource hardening candidate

Base: user-validated run #1075, Brave `44a84b1f89d9a35287289d6a3d493e362f5a5123` (v1.98.62). Vendored engine manifests identify adblock **0.13.3**, correcting earlier analysis that said 0.13.0.

## Evidence and limits

The Hindu test succeeded with a three-rule request-path override. This implicates that path but does not prove that `noop.js` was missing on the phone. The renderer SIGABRT is a separate Blink invariant failure. No assertion is disabled by this patch, and no site-specific exception is shipped.

The pinned provider can return empty resources before its signed component is ready. Cached DAT rules are published before resource loading. Resource-only asynchronous merges also lack the existing filter-build generation guard.

## Implemented changes

- Self-authored, unprivileged `noop.js`/`noopjs` bootstrap for rules that **explicitly request this resource**. This is not a replacement for arbitrary unknown scripts or a global allow rule.
- Same-engine JSON/parser validation for component updates: an empty, unparsable or wholly unusable bundle does not overwrite current known-good resources. Individual resource failures retain upstream semantics; duplicate aliases or unresolved optional dependencies do not reject an otherwise usable bundle. This deliberately avoids imposing a new untested whole-bundle compatibility requirement.
- Component generation check prevents a stale disk read from replacing the latest update.
- Custom-resource merges re-request the current generation rather than publishing old asynchronous merge results. Existing custom-resource developer-mode/permission restrictions remain intact.
- Cached DAT publication waits for a resource snapshot and is discarded when a newer filter build supersedes it.
- Unknown redirects retain upstream matching behavior. No `$important`, trust-mask, filter preference, or Shields semantics are relaxed.

## Scope intentionally not claimed

- Last-known-good retention is **in-process**. The signed component updater persists its own downloaded component, but this patch does not add a new persistent atomic rules/resources generation store.
- Bootstrap provides only the generic no-op redirect. Full scriptlet/redirect coverage still requires the normal signed resource component. Native filter lists need not be enabled for resource components to work.
- This does not establish compatibility with every current uBO or AdGuard rule, nor prove that synthetic responses satisfy every page's MIME/CORS/CSP requirements.
- This is not a verified fix for the observed renderer assertion.

## Integration

Apply after the final `apply-sandium-adblock-engine-race.py` pass (overlay28 in #1075), never before the overlay25 shared-source reset. The original race verifier expects its old DAT sequence; run it before this patch. Repeated application of this patch itself is idempotent. Prepared source must be rebuilt from the pinned reset on future complete overlay cycles.

## Validation

Passed: nine offline source-contract tests; exact pinned-source transformation + engine-race composition applied twice. Tests preserve fixture MPL notices and hashes.

Added but **not executed**: C++ provider tests for bootstrap, malformed update preservation and stale read rejection. Normal APK compilation does not execute unit tests. The current environment has no Rust/C++ Android toolchain, so native compilation, unit execution, Android proxy-response tests, offline lifecycle and device-site validation remain pending.

Required device validation: remove the temporary Hindu override; enable AdGuard Ads; cold/warm/offline start; test article and other script redirects; confirm component updates preserve full scriptlets. Keep original APK available for rollback.
