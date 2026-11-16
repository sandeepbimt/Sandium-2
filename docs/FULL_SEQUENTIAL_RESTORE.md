# Sequential ordinary Full restore

#1199 verified all eight base archives but ran out of local space during base
extraction. Five shard extractors succeeded and three failed. All seven delta
ZIPs had already been prefetched, so post-extraction cleanup could not help that
peak. This is evidence of local disk pressure, not remote artifact quota.

Ordinary Full stages now use these explicit phases:

1. `restore-base`: validate selected plan and exact base manifest; require fresh
   disposable workspace/state; verify/extract all eight shards with the existing
   legacy implementation, then release only their exact local compressed files.
2. Restore one immutable delta cache, then `restore-layer --slot N`: verify its
   envelope against the selected plan; require the exact cursor/parent; perform
   unchanged sparse SHA/topology/staging verification and replay; release that
   local ZIP only after success. No future ZIPs need be resident at that point.
3. `restore-finish`: require exact final head and completed layer count, then
   write the normal restored proof used by begin/capture.

Progress is bound to the selected receipt. A busy marker is saved before any
mutating base/layer operation. Failure or interruption cannot be retried against
that partially replayed tree; use a fresh job restoring the unchanged remote
accepted checkpoint. Unused slots skip only after every required layer completes.
No remote cache deletion, base fallback, checkpoint expiry reset, or relaxed disk,
hash, parent or topology guard is introduced. Generic and maintenance restore
paths remain unchanged. The existing conservative cache-selection guard is also
unchanged. Bytes and available inode telemetry distinguishes later disk failures.

Host tests exercise real delta replay and subsequent capture, binding/order,
corrupt delta, interrupted base, symlink input, repeated operations and premature
finish. Legacy extraction is mocked with a base clone in these new tests; its
existing tests still apply. End-to-end CircleCI peak and build outcome remain
unverified until a separately authorized run.
