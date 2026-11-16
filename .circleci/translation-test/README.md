# Isolated ARM-on-x86 JNI experiment

This branch builds the normal ARM64 Release product plus one experimental JNI
compatibility guard. It is **not a native x86_64 product** and is not a phone
release. The runtime guard and its scope are documented separately by the patch.

`build_config.py` deterministically derives the experiment's config from the
unchanged normal Full candidate. Run it after updates to that candidate. It writes
`translation-test/config.yml`, its SHA256, and this branch's `.circleci/config.yml`.
The normal candidate, generator and checksum remain unchanged.

Isolation rules:

- Only `experiment/arm-translation-guard` can run the test build, and `run_build`
  still defaults false. Use `run_maintenance=false`.
- Normal accepted ARM reference and source/tool caches are read-only inputs.
- The only cache writes are branch/workflow-bound stage handoffs and
  branch/revision/workflow-bound APK completion markers. They cannot become the
  normal branch's checkpoint or completion marker.
- No fixed-reference renewal/maintenance job exists in the test configuration.
- Shared accepted-reference, Node and apt cache saves are removed.
- Build flags/output directory and normal graph/remote execution/validation gates
  are unchanged. This deliberately reuses the existing ARM64 compiled base.
- Artifacts are labeled `sandium-arm-translation-test-only` in this run. The APK
  filename/package remains native product-compatible; do not confuse this with a
  normal release just because the installed package name is identical.
- Content-addressed BuildBuddy cache behavior remains native and unchanged. The
  changed source produces different action digests; reference checkpoint metadata
  and files are not promoted.

Guard application runs after all normal product reset/overlay work and before GN
validation/compilation. A runtime branch assertion fails closed outside this test
branch. `flow_wiring.py` accepts either the exact normal config checksum or the
exact separate experiment fixture/checksum; unknown mutations still fail closed.

Tests: `python3 -m unittest discover -s tests -p test_translation_test_isolation.py`
plus normal canonical suites. The canonical runner deliberately verifies the
normal config fixture in a temporary checkout; the isolation tests independently
verify this derived config and its unchanged compilation/publication gates.

Restore integrity is captured after archive extraction, fixed-reference postrestore
validation, and reference selection, but **before** pinned-source preparation and
product overlays. Those steps legitimately regenerate GN arguments and outputs;
comparing after them falsely reports checkpoint corruption. The existing byte/hash/count criteria are preserved; a missing same-workflow
prior report now fails closed in continuation stages. No outputs are deleted
or cache reuse disabled; later graph/remote-execution gates remain in place.
