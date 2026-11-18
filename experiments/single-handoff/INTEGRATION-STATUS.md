# Integrated source candidate: first experimental compile enabled

The enabled code path now plans the whole candidate, not the earlier two-stage
subset. The user-authorized experimental profile and branch gates are prepared
for the first compilation. Publication and CI outcomes must be verified separately.

## Included source mechanisms

- Native Chromium web navigation/paint holding with the optional blur overlay disabled.
- History/native-page callback ownership, cancellation and once-only acknowledgments.
- Bounded native-home-to-web child retention, destination identity/geometry/presentation
  observations, toolbar/window safety, input/accessibility isolation and cleanup.
- Native-home wallpaper selection/request ownership and immediate measured preparation.
- Document-scoped dark policy authority through preferences, commit, BFCache and prerender,
  preserving existing typography transport and methods.
- Real source staging, component/GN registration and exact journal rollback including new files.

## Verified here

Focused host tests compile actual injected Java/C++ methods against explicit API doubles.
Sanitizer checks use ASan/UBSan; LeakSanitizer is unavailable in the executor.
The real final styled/diagnostic UI composition, deterministic replay, native-baseline
whole-candidate equivalence and exact rollback pass. These are source/host checks.

## Not established

No real GN/JNI/Mojo generation, Chromium Android compilation, APK installation or device
rendering/performance validation has run. Cold home wallpaper decode can still require
native opaque backing. Chromium's native slow/error/empty-page safety limits remain.
General toolbar shake elimination and universal flash-free transitions are not proven.
This is an integrated implementation candidate, not a claim that every requested visual
outcome has been achieved. The first run validates the integrated implementation;
it is not a claim of proven flash-free behavior.
