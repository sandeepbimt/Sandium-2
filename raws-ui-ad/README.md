# RawS ad UI source overlay

This experiment uses two existing production #1471 facilities: the real packaged
engine initialization phase and the official built-in filter subscription
refresh path. It does not change network, cosmetic, popup or redirect decisions
or add navigation delays. It reports **built-in ad filtering active** only once
native initialization is successful. It does not report that all remote
subscriptions are loaded. Screens read the phase on presentation/resume.
Filter-list refresh is a request, not a success notification: the regular profile
action only accepts when ready, started and not busy, for at least one available
list, at most once per minute. Last-known-good rules stay in use until a valid
replacement loads.

No implied on/off, per-site scope, popup controls, or counters. The existing
backend does not expose complete native controls for all those paths.

Run the generator from this source checkout against a separate exact #1471
checkout followed by the Chromium 52bdd217 `chrome/android/BUILD.gn` file
(official Git blob e3e9d0318a10d0988fbb30cdc4bd38d372d4cf2e), and a new target
directory outside that checkout:
```
python3 raws-ui-ad/compose.py /path/to/exact-1471 /path/to/BUILD.gn /path/to/new-delta
RAWS_AD_UI_DELTA=/path/to/new-delta python3 -B raws-ui-ad/test_composition.py -v
```
The inputs are SHA-256 checked; existing recipe, pins, navigation, admission and
CI are untouched. `ad-ui-receipt.json` identifies preview input/output hashes.
It is not an admission manifest. To integrate, compose this and other reviewed
outputs with tested preimage equality, re-seal the exact full manifest and
admission, and verify the generated JNI path as well as the existing Java/UI
and native engine graph. Preserve the exact engine snapshot and protected
checkpoint. No publication approval is represented by these source files.

Host tests compile extracted native phase/refresh behavior and generated Java
status mapper against substitutes, plus validate linkage source references and
preference XML. They do not verify the Android compiler, actual JNI generation,
browser behavior on-device or a signed APK.
