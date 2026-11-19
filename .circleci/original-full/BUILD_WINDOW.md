# Full compile window

2026-11-18: User approved increasing the Full compile slice from 20 to 25 minutes (1500 seconds), effective next run. Existing jobs retain their original configuration. Fast mode is unchanged.

Measured phone pipeline 1350 stage 1: preparation 14m55s, compile and shutdown 20m13s, checkpoint validation/archive/upload 13m04s, total 48m13s. Five extra compile minutes project 53m13s with similar overhead. This is not a guarantee: checkpoint and remote execution timing vary. Thirty minutes would leave inadequate headroom against the 60-minute job budget.

The supervisor still stops promptly on true failures, attests only actual time-slice expiry, and allows up to 60 seconds for orderly process shutdown. Verified APK publication still skips the large handoff. No unrelated pipeline behavior changes.

## Same-pin Official normal Full follow-up after #1416

The older exceptional-run supervisor overrode the nominal Stage 1 budget with
a 12-minute cap. #1416 hit that cap rather than a compiler failure. Future
normal Full Stage 1 runs target 25 minutes, with the compile giving time back
only if setup exceeds 17 minutes. Reserve 18 minutes of the 60-minute job for
the existing archive/handoff path. The same-pin #1402 validation, packing and
upload took 16m14s; at #1416's 18m17s setup the new allowance would be 23m43s.
These timings are a planning baseline, not an upload guarantee. Stages 2–5,
APK/checkpoint rules, cache keys and the frozen #1402 restore point are unchanged.
