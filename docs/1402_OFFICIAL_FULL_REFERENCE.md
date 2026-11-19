# Official Full reference: completed #1402 stage 2

Scope: only future same-pin Official Full runs on `fix/1394-official-lint`.
This is not a RawS, latest-Brave, or project-global reference change.

- Source: `af15f567826041b83fb9295b12b3aa0d7c4b74ad`.
- Producing workflow: `07214cac-daf8-47f1-a9dd-b48d229e934f`, stage 2.
- Cache: `sandium-official-handoff-v1-fix/1394-official-lint-07214cac-daf8-47f1-a9dd-b48d229e934f-stage-2`.
- Eight independently compressed shards, 35,755,833,859 bytes; manifest SHA-256 `d6f47ee140ae7ec0ef36448f767e2fd90b1370da4e9bdae8673bd3fd93f47749`.
- APK: 365,446,122 bytes, SHA-256 `db8a86a10c317a5c2fc806cd15ff01d2d23fe1f906c1648bf5e0c6a6e3cc09a9`.
- Independent fresh readback #1410 verified manifest, shard hashes and zstd integrity,
  fresh restore, Chromium/Brave source and official GN identity, and APK bytes/ZIP integrity.
  This is restore evidence, not a new build or device test.

Each future Full stage 1 validates the exact digest/provenance and all eight shard hashes
before extraction, and checks restored engine, GN and APK identity before product patches.
It then removes only the seed APK and its local completion markers, preserving the build
graph, objects and checkpoint provenance; an old APK must not complete a new build.
Later stages retain current-workflow handoff/early-exit and post-APK archive behavior.

The previous #1401 stage 1 seed is preserved, not deleted or a silent fallback:
`sandium-official-handoff-v1-fix/1394-official-lint-2e04b4eb-d8c4-4d0e-af5f-e19e8fb77fd6-stage-1`.
See `1401_REPAIR_RECORD.md` for the prior identities. Revert this scoped promotion
explicitly to return to the previously tested, incomplete #1401 continuation behavior.
