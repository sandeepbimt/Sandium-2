# Separate official-mode reference over #1389

Frozen tested phone baseline remains remote `315d78c8a1c98dd845d640203a1912213c1bedad` (#1389). This branch does not replace or promote that release or RawS.

## Contents

- All #1389 navigation, menu, homepage, Shields and typography source preserved.
- Reviewed narrow screenshot-origin correction for settled **unwrapped regular NTP with bottom toolbar**. Unsupported geometries retain existing behavior. Not a universal homepage or blue-flash fix.
- Reviewed bounded ordered diagnostic writer: normal event appends off caller thread, RAM export retained, stopped/interrupted recording never silently resumes. Queued crash-tail loss and pending private-file deletion are explicitly reported. Initialization remains synchronous.
- No renderer recoloring, skipped clear, custom black overlay or speculative blue-flash patch. Earlier diagnostic recolor was reverted.

## Genuine official GN mode, not vendor release identity

`is_official_build=true`, `is_debug=false`, `is_component_build=false`.
Pinned release expectations are explicit: DCHECK/configurable/expensive checks and Java assertions off; ThinLTO and LLD on; mold off; symbol level1. CI validates wrapper-generated inputs **and GN-resolved values** before compilation, without dumping unrelated credentials. The pinned `//components/viz/service:service` target owning SkiaRenderer is also checked for `NDEBUG`, absence of `DCHECK_ALWAYS_ON`, and ThinLTO compiler flags. This establishes generated target configuration, not device behavior.

Brave's supported local Release configuration keeps `is_brave_release_build=0` and `chrome_pgo_phase=0`: no proprietary production profile download or Brave signing key is required. This is a Sandium official-mode reference, **not a reproduction of the distributed Brave APK**. Package, signing configuration, arm64-only choice and Sandium branding remain unchanged. APK signature/install compatibility must still be checked on the produced artifact.

This build difference is a source-backed candidate explanation for diagnostic blue paint. A clean result would support that explanation; it would not prove all compositor/navigation defects gone. No measured performance improvement is claimed beforehand.

## Isolation and resource constraints

The fixed nonofficial archive is a verified **read-only source seed**, not an official-compatible compiled checkpoint. Full product preparation regenerates GN, causing broad native recompilation. Official handoff/APK keys are separate and workflow-scoped; no automatic stable-reference promotion or fixed metadata write. Existing source/toolchain pins, archive validation, eight archive workers, five sequential stages and 25-minute compile slices remain.

ThinLTO adds linker work; a final link could exceed a slice. No duration/RAM guarantee is made. Existing sharding excludes only transient `*.staging`, so completed output/ThinLTO cache files are retained in checkpoints. Do not silently relax time limits, discard incomplete archives, or claim compile success from host tests.

## Validation boundary

Local source/host regressions and independent reviews do not substitute for GN generation, generated JNI/Mojo compilation, linking, APK signature checks or device behavior. The first authorized CI run performs those validations. Keep #1389 available for rollback and compare the same navigation sequence on the same device.
