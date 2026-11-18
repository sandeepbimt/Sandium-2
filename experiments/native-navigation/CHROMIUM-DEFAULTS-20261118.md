# Standard pinned Chromium navigation, native blur enabled

User-directed replacement for canceled navigation diagnostic pipeline1380. Reference is Chromium d331de35ca8ab1358c7a17e4bd41627d55eaef51, not Brave navigation preferences.

The transactional profile restores ordinary blur implementation, predictive Back/Forward screenshot/cache/fallback animation, native controls/inset geometry, and Settings motion. All engine postimages have byte-exact pinned comparisons; injected numeric diagnostics can be stripped to those originals. The earlier Sandium blur lifetime repair is intentionally removed together with all custom navigation behavior, not silently retained.

## Explicit retained deviations

- Chromium's blur flag is disabled by default. At the user's request we enable its bare feature, with unchanged native hold350ms, fade150ms, sigma3.0. No strength/hold overrides; saved Sandium blur/darken settings remain stored but disabled and ineffective. Explicit developer command-line opt-out remains respected.
- Sandium fallback icon, wallpaper, shortcuts, address capsule styling/location and opaque status paint remain. No legacy transparent-status gradient is introduced.
- Disabled-feed readiness adapter remains because Sandium has no feed to restore. Native smooth alpha delegate and its completion lifecycle remain.
- Opt-in numeric diagnostics remain. Native mode omits Sandium-only native bitmap source/layer events; unavailable blur top-control offset is -1, not fabricated zero. Native reveal bounds/controls samples remain enabled only during an opted-in recording.

Native behavior does not promise every Back entry is cached or remove all possible fallback/white frames. The four-second fallback and homepage jump still require device evidence. This is an intentional native baseline comparison, not a claim those symptoms are resolved.

## Transaction order and rollback

Existing product overlays and their diagnostics run first. Native profile strips only recognized transition probes, restores exact pinned bodies, and adds compatible numeric probes before journaling final postimages. Unknown probes fail before writes. On next replay, journal rollback restores exact diagnosed product preimages; ordinary diagnostic reset then strips their probes. This preserves existing reset order and other feature work. Settings restoration participates in the same fail-closed journal.

Set profile enabled=false and replay to return to the frozen customized product. Unknown later source edits block destructive rollback. Never directly revert the generated source or apply new profile over an old un-restored journal.

## Validation

Host assertions cover exact native engine code, narrow startup/icon exceptions, compiled bare-feature activation, diagnosed on/off round-trip, unknown-probe rejection, Settings/inset restoration, original Full wiring and completion markers. Android build and on-device navigation checks remain required.
