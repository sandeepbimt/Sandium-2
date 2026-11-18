# #1401 lint continuation

Published input: 75771fab8d021eba0161d7ad5cf1c4a99f37a9b8.
Workflow: 2e04b4eb-d8c4-4d0e-af5f-e19e8fb77fd6.
Stage1 job4290 passed; stage2 job4291 failed lint: 644 newly exposed unused resources, 2 PluralsCandidate, 4 TypographyEllipsis. None of644 matches previous320 reviewed resources. Prior exceptions worked. No verified APK or completed post-APK archive.

Exact successful stage1 checkpoint cache:
`sandium-official-handoff-v1-fix/1394-official-lint-2e04b4eb-d8c4-4d0e-af5f-e19e8fb77fd6-stage-1`

Validation log: CHECKPOINT_SAVE=PASS, officialRelease/ThinLTO gates PASS, incompleteAPK flags false. Source revision75771fab, stage1, same engine Bravev1.98.62 / Chromiumd331de35ca8ab1358c7a17e4bd41627d55eaef51. 8shards,35678309172bytes, source75332407311bytes. ManifestSHA256 5a422405fb05505a99d1ea3f94ca95de5fe61f8c7abe3888b97ec47726fdd5e3. Cache upload28GiB completed; stage2 restore+extraction passed. This is an incomplete compatible checkpoint, NOT an APK-ready reference. Prior1394 reference remains preserved.

New run validates exact provenance, eight shard hashes and official GN before replay; no broad cache fallback. Final APK and full archive still required; no success or promotion claimed.
