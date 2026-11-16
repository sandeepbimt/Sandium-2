# Explicitly requested fail-fast deviation (16 November 2026)

This supersedes the original Full behavior that allowed action failures to be
archived and handed to later stages. A failed build command now records failure
and returns its nonzero exit status. CircleCI's normal on-success sequencing
skips export, archive and cache-save work; dependent stages cannot start.
The two former always-run APK marker operations are now on-success too.
Small existing exit-trap diagnostics and CircleCI diagnostic artifact handling
are not workspace archive/reference publication and remain available.

The process-group budget supervisor attests command timeout; the separate
allowed budget boundary is successful CAS recovery returning after the shared
deadline, leaving no time to resume. That boundary requires recovery exit zero
and is not evidence of APK completion. In either case, a child's own
124, interrupt, OOM-like137 or SIGTERM143 is a failure, not a completed slice.
At genuine budget expiry the supervisor sends SIGINT, waits up to60seconds,
then SIGKILL if necessary. Existing bounded CAS recovery remains; exhaustion
before unresolved recovery remains failure. Successful recovery consuming the
remaining budget is an incomplete handoff, never APK success.

Normal1200second Full slices,8-worker stage handoffs, fixed reference identity,
source pins/hash checks and expiry-only renewal are otherwise unchanged.

Tests execute the actual generated build body with stub preflight dependencies,
including real short deadline expiry, spontaneous failure/signals, child124,
stale timeout marker rejection and supervisor cancellation. This is not a live
CircleCI/native Android compile or service-level cancellation test.
