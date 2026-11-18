# Reversible pinned Chromium navigation profile

Current activated scope: [standard Chromium with native blur enabled](CHROMIUM-DEFAULTS-20261118.md).

Frozen Sandium navigation cut-off: **a6863ec**. Chromium
`d331de35ca8ab1358c7a17e4bd41627d55eaef51`, Brave
`44a84b1f89d9a35287289d6a3d493e362f5a5123`.

Before ANY ordinary overlay replay/resume (each overlay24–30 entry), run the tool
with `--mode off` to restore a previous experiment journal. Native paint must not
be fed directly into the normal scroll-status transformer. Successful off retires
the journal to `.restored`; next on captures the latest normal-overlay result.

Apply on only AFTER all ordinary frozen overlays, homepage/capture changes and their
verification, and BEFORE final graph validation/compilation. `profile.json` is the
single on/off switch. No experimental per-axis ownership/ACK code is involved.

```
python3 experiments/native-navigation/apply.py "$SRC" --mode configured
python3 experiments/native-navigation/apply.py "$SRC" --mode configured --verify-only
```

CLI `--mode on` refuses to proceed without the independently reviewed native
geometry module. This is an experiment requiring phone comparison, not a claim
that the shake or flashes have been fixed.

## Native paths restored

- Predictive Back/Forward screenshot acquisition, availability guards, preview
  eligibility, compositor occlusion behavior, cache metadata, native cache-miss
  fallback and preview-to-live animation. Native BFCache/navigation controller
  remains responsible for history; no invented history-cache mechanism.
- Ordinary navigation blur manager and its native feature parameters. Custom
  outgoing blur/darken/fallback modifications removed. Startup enables the bare native blur feature without parameter overrides. Existing custom blur/darken preference values remain
  saved but their controls are disabled during the comparison.
- Native gesture SHOWN ordering was already restored in frozen Sandium and remains.
- Native inset/control geometry reset is supplied by `geometry.py`; existing opaque status paint is retained; legacy gradient overrides are excluded. **Web content scroll-under-status is unavailable in
  this native-geometry comparison.**

## Customizations deliberately preserved

Wallpaper, homepage shortcuts, lighter/taller address capsule, transparent surround,
menu/picker improvements, native forward button wiring, dark-page policy and
adblocking. Ordinary page loads/address-bar/search/external-link navigation already
call native controllers and are not replaced by a second navigation implementation.

The disabled-feed NO_STATE_TO_RESTORE adapter remains because Sandium removes the
feed; copying its native feed-wait supplier blindly could stall the homepage.
Native smooth delegate fade/cancel/view lifecycle remains. Settings motion is restored as part of the transaction. Custom homepage backing,
forward-button capture coherence, bottom-toolbar placement/focus choices remain
and are explicit comparison differences, not falsely labeled pristine Brave UI.
Native cache-miss fallback can still be visible when a usable screenshot is absent.

## Exact rollback

Before any writes, the tool validates all anchors and journals the complete before
and after text plus SHA256 for every changed file under the source root. `off`
restores those exact frozen preimages; files outside this manifest are untouched.
This preserves menu/picker/other fixes that preceded experiment activation. A
fresh source tree with the switch off simply retains normal product overlays.

Re-running on/off supports files in either recorded state (including interrupted
writes). Unknown edits after activation cause a fail-closed error instead of
silently overwriting work. A changed experiment recipe also blocks reactivation
until its old snapshot is restored. Thus new same-file fixes need explicit rebase
onto the frozen product overlays, not a destructive blanket git revert.

## Validation

Four host tests: exact pinned-native transition parity; on/off byte equivalence
with preexisting unrelated edits retained; unknown later edit blocks rollback
without partial writes; late invalid anchor writes nothing. Fixtures contain full
pinned transition sources, Brave patches for affected native features/NTP, and
compact UI anchors. Geometry has separate tests and requires combined replay.
Native Java/C++ compilation and Android visual tests are still required.
