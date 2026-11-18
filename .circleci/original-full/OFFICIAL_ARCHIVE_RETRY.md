# Exceptional #1392 archive retry

#1392 failed in shard creation, not a timeout: zstd exit 70, ENOSPC.
The 71 GiB workspace had only 30 GiB free while its incoming compressed
checkpoint was still retained. Seven completed shards totalled 30,307,076,421
bytes; shard 02 failed and the manifest/cache save was not published.

This isolated branch preserves product code and official compiler settings.
After successful extraction, pin verification and build-mode validation, it
rechecks all eight incoming shard hashes, records their manifest in the local
workspace, then deletes only those regular local transport files. It refuses
unexpected files or symlinks. Remote frozen cache and all source/build outputs
remain untouched. Legacy tar cleanup is deliberately unsupported.

The nominal compile ceiling remains 25 minutes, but the first stage is capped
at 12 minutes. All stages reserve 28 minutes against a conservative 60-minute
job window for termination, validation, archive, upload and safety. This is a
budget policy, not a guarantee of CircleCI upload speed. Insufficient time fails
closed. Disk checks require 50 GiB after cleanup and, before packing, at least
max(40 GiB, 65% of current source bytes + 4 GiB). Compression estimates cannot
guarantee a worst-case incompressible workspace fits.

Unlike ordinary APK delivery, successful APK publication does NOT halt this
job. The full eight-shard archive and existing receipt checks must complete and
be saved. Downstream stages may halt only after this successful prerequisite
job. No automatic stable-reference promotion is added. A later isolated
readback/verification is still required before selecting this as a new restore
point. The previous frozen reference is retained.

No #1392 complete checkpoint exists to restore. Retry starts from the previous
verified reference; BuildBuddy action-cache reuse may reduce recompilation but
is not a substitute for a complete checkpoint.
