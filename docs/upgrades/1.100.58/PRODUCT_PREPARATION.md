# Exact158 product preparation admission

The product adapter is admitted to **attempt** preparation. The top-level upgrade
profile remains held separately. No local GN generation, Android compilation,
APK, or device-success claim follows from this admission.

## Verified source work

- Exact Brave `bd6d26d1bced03c17a98baa86d2cd3425d543d1b` and Chromium
  `52bdd21723d5db0c9ab11716d38feac74828cf84` inputs were Git-blob verified.
- Production reset replay passed for 353 Brave inputs, 153 Chromium inputs and 24
  official Brave patches. Reset provenance and focused patch fixtures are checked
  into `tests/fixtures/upgrade1100`.
- Complete ordered source composition passed: UI, all 16 removal steps, home,
  video, dark/manual policy, page text, diagnostics, native/outer navigation,
  resets, interruption recovery, journal verification and exact rollback.
- The target test rejects historical native/holder/bridge fallback bytes. Its
  target journals receive the actual 158 pair. Startup checks the final Off/On
  native policy rather than the retired forced-off marker.
- The local composition used a Git-blob-checked reader for official upstream
  source, not mocked transformation success. The optional GN formatting pass was
  not run locally. CI runs the same composition script with real source repos
  and the synced GN executable.

## Runtime interface

`python3 .circleci/upgrades/product.py prepare|verify|plan --root PROJECT`

The caller explicitly prepares host dependencies and verified Node/pnpm, supplies
`FULL_U_SCOPE`, `CIRCLE_SHA1` and deadline/process-group ownership. Verification
never installs host packages, syncs sources, resets overlays or generates GN.

Preparation unwinds journals, resets owned sources, retires the old reader,
replays base overlays and 24..30, then performs toolchain normalization, fresh
native official GN, resolved verification and all removal graph audits. Target
step 30 does source removal only; legacy step 30 behavior is retained separately.
The native compilation target is `brave`; no invented APK alias is used.

Only successful final GN/audits create
`brave-work/.sandium/full-u-product-ready.json`. This binds scope, source proof,
`build.ninja`, recursive literal GN argument imports (including mandatory
`args_generated.gni`) and archived graph evidence. Unresolved dynamic or escaping
argument imports fail closed. The canonical receipt/reports live under
`brave-work/.sandium/product-graph/`, not unarchived root artifact directories.

A new preparation attempt clears an old ready claim before source writes. Failure
preserves the source-owned receipt but cannot manufacture build readiness. Runtime
GN/lint/compilation may still expose new diagnostics; their gates remain enabled.
