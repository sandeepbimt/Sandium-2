# Fixed reference metadata gates (inactive candidate)

This helper performs no cache restore/save, deletion, publication or CI action.
Its input accepted receipt must come from the existing trusted exact cache
selection, not an untrusted arbitrary JSON file. Envelope SHA validates integrity,
not cryptographic authorship.

`bootstrap(receipt, scope, now)` reads ONLY `plan.base`, enforcing expected scope,
compatibility and legacy kind, exact approved physical cache, 32,775,343,758 bytes,
and recorded conservative 2026-11-29 08:22:53 UTC deadline. It deliberately does
not use delta heads or expired delta dependencies, because no delta is restored.
The logical receipt key is UTF-8 without appended newline; CircleCI's cache
checksum suffix is represented as base64 SHA-256 with slash replaced by underscore (plus retained). Actual receipt-to-cache
mapping must be corroborated at integration. No actual manifest SHA is hardcoded
or invented; it must come from the accepted receipt and match the cache manifest.

The candidate is not accepted metadata. `accept_bootstrap` requires the exact
manifest hash/base ID, eight shards and expected total byte size, the original
legacy compressed-shard hash verifier, and the pinned Chromium/Brave HEADs from
the successfully extracted source before preparation. Missing or different
metadata fails closed.

Renewal is allowed only within two days of the immutable deadline, while still
unexpired. It proposes a distinct immutable cache key and conservative creation
+14-day deadline. All content identities remain unchanged. Caller orchestration
must save the identical verified files, clear disposable local readback inputs,
restore the exact new immutable key without prefix fallback, and call
`accept_renewal` on those restored files. It verifies every shard again, checks
unchanged identity, and rechecks the creation/due/expiry gates. Only then may the
caller atomically publish the returned reference record. No old remote cache is
deleted. Reopening an old record or restoring it never extends expiry.

Six local tests cover exact metadata, digest/expiry rejection, key byte semantics,
source-pin gate, due-only unchanged-content renewal and shard-verifier execution.
They do not download the 32.8 GB cache, prove actual native cache save/readback,
or activate a schedule. Those integration gates remain required.

## CLI contract

All phases require `--root JOB_ROOT --legacy-script SCRIPT`. State lives in
`.fixed-reference`. `select --legacy-receipt EXACT_PATH` uses existing
`accepted.json` if present (ignoring the legacy path), otherwise strict-scope
bootstrap. It writes `selected.json` and exact logical UTF-8 bytes in `cache.key`.
Native restore uses `sandium-bridge-base-v1-{{ checksum ".fixed-reference/cache.key" }}`.
`preverify` validates downloaded archives; `postrestore` validates extracted pins
and accepts bootstrap. Already-accepted metadata and its ID stay byte-identical.

Maintenance requires accepted metadata. `renewal-check` writes `renewal-due`
(`yes`/`no`); caller must halt before a large restore when `no`. After restoring
and verifying the old exact cache, `renewal-prepare --new-logical-key UNIQUE_KEY`
writes `renewal.json` and switches `cache.key` to the new logical bytes. Native
save must complete before `renewal-clear`; that phase verifies old identical
payloads against the candidate, then removes only the manifest and eight local
archive files, with a candidate-bound ready marker. Native exact-key restore must
follow. `renewal-accept` requires that marker, revalidates payloads and publishes
only local `accepted.json`. Caller then saves accepted metadata natively. No
phase itself invokes CircleCI or modifies a remote cache.
