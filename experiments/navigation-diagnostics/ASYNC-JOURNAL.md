# Bounded asynchronous diagnostic journal

## Source-supported performance issue

In recorded build 315d78c8a1c98dd845d640203a1912213c1bedad, every accepted diagnostic event synchronously serialized, CRC-framed, opened, appended and closed the private journal under the recorder class monitor. Native ad producers explicitly run on BrowserThread::UI and call JNI directly. JSON4 contains 1,119 rows, approximately 143,239 framed bytes: 1,119 logical append/open/close sequences, plus state records. This does not measure filesystem latency or prove that recording caused any particular loading delay.

## New ownership

The recorder still validates, copies and appends bounded numeric Rows to RAM synchronously. It serializes immutable CRC-framed byte records, but a single dedicated daemon owns filesystem append, reset and deletion. Consecutive append commands batch up to 64 records/64KiB of accounted bytes. Pending work is bounded by 256KiB of payload-plus-fixed-metadata accounting and 2,048 commands including the active batch. These are queue accounting limits, not an exact JVM heap measurement; Row storage retains its existing 5,000-event cap.

There is no UI wait, join, flush or disk operation in record/stop/start/clear. Initialization/recovery still performs the existing bounded one-time private-file read; it is not falsely described as fully asynchronous startup. Thread launch and small in-memory serialization remain on the caller, so no zero-overhead claim is made.

Start/clear supersede queued old-epoch work. A currently executing old batch finishes before the worker handles the new reset/delete; stale completion/error cannot mutate the new recorder epoch. Queue overflow stops recording with persistence_queue_full/queue_overflow and an explicit rejected-record count, rather than blocking the UI or growing memory indefinitely. I/O error stops recording without retry loops. The queue monitor is never held while taking the recorder monitor or performing disk work.

## Export and durability

Export already freezes snapshotJson from RAM after stop and writes the chosen document through the UI's existing background file executor. It remains complete for accepted in-memory events without waiting for the private journal. Export includes journal_async, pending commands/bytes, last-written command sequence, rejected records and recovered-tail uncertainty; an exported RAM snapshot is not a claim that every event has reached the journal.

Stop enqueues ordered terminal state. Clear shows clearing until actual background deletion succeeds, then cleared; existing UI refresh runs every second. A process killed before pending clear completes may leave the previous app-private journal. The pending state must not be presented as completed erasure. No application can guarantee queued work survives process death; no synchronous UI flush is introduced to hide that fact.

Schema3 preserves the existing CRC record body and reads schema2. After interrupted recording, recovery retains a valid prefix, marks recovered_async_prefix/recovered_async_tail_unknown and does not silently resume. A truncated CRC tail remains recovered_partial. A persisted terminal stop follows all earlier journal records; it does not imply fsync durability against device power loss. Header creation retains its existing fsync, now on the worker.

## Validation

Actual Java tests block the worker while proving caller recording/stop/snapshot/clear/start complete, check epoch supersession and private-context suppression, force bounded overflow and filesystem errors, kill a separate process, recover CRC prefixes, and verify completed clear. Test-only barriers never enter product APIs. Existing cap, incompatible-build/schema, rollback-clock and compile-contract tests remain. This is host validation, not an Android throughput benchmark or a quantified page-loading improvement.
