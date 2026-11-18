# Full compile window

2026-11-18: User approved increasing the Full compile slice from 20 to 25 minutes (1500 seconds), effective next run. Existing jobs retain their original configuration. Fast mode is unchanged.

Measured phone pipeline 1350 stage 1: preparation 14m55s, compile and shutdown 20m13s, checkpoint validation/archive/upload 13m04s, total 48m13s. Five extra compile minutes project 53m13s with similar overhead. This is not a guarantee: checkpoint and remote execution timing vary. Thirty minutes would leave inadequate headroom against the 60-minute job budget.

The supervisor still stops promptly on true failures, attests only actual time-slice expiry, and allows up to 60 seconds for orderly process shutdown. Verified APK publication still skips the large handoff. No unrelated pipeline behavior changes.
