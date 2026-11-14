# Build 1154: Playlist-only R8 rule closure

The combined build passed the prior Java errors and reached final dex: 4646 actions completed, one failed, 19 remained. R8 rejected a stale keep rule for `com.google.gson.reflect.TypeToken`; the pinned source explicitly documents this rule as needed by the prebuilt Playlist AAR, which this product excludes. The pipeline saved its incremental checkpoint before rejecting the deterministic failure. No APK was produced.

Remove only the exact pinned Playlist-only rule and its explanatory comment. Keep warnings-as-errors and all other shrinker rules unchanged. Add proguard.flags to pinned reset/replay so stale checkpoints cannot retain an incompatible version. A missing/mutated source anchor must fail instead of silently skipping the patch.

205 unit tests and full pinned UI/removal composition, reset/replay and interrupted recovery passed. Independent source review passed. Actual R8 and device verification remain outstanding.
