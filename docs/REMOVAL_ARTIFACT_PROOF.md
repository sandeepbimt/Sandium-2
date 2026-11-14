# Removal artifact evidence: exact scope

The APK audit is a **six-group class-definition denylist**, not proof that all thirteen
components have disappeared. It scans every packaged `.dex`, rejects malformed tables,
unsupported DEX formats, duplicate entries/classes and empty class inventories. Original
class names appearing only as references are not counted as implementations.

The JSON result binds the APK SHA-256 and byte size. With `--recipe`, it also binds the
13-group recipe hash and upstream pins. This binding does not establish that the graph
was generated from that recipe. The separate graph receipt must establish that link.
The report always leaves `all_13_removed_verified` and `native_and_runtime_verified` false.

## Obfuscation

`--mapping PATH` optionally checks original class names recovered from an R8/ProGuard
mapping against class definitions actually packaged in the APK. Mapping provenance must
be tied to the same build by the caller. An absent mapping is explicitly reported as
unchecked; an empty or ambiguous supplied mapping fails. A mapping entry for an absent
class is not evidence that its implementation shipped. No speculative filename guessing
or blanket removal of strings containing "ads" or "Brave" is used.

## Required complementary evidence

- Fresh generated dependency/source closure, low-coupling six-group and Leo reports,
  tied to current source revision, recipe and effective GN configuration.
- Retained protocol/interface compatibility sources checked against the pinned allowlist.
- Exclusive resources/Android manifest services/providers/jobs and native link inputs
  reviewed separately. A class-prefix audit cannot substitute for these checks.
- Recipe and graph-receipt hashes must match the export report and exact APK hash;
  stale reports and previous-product APK completion markers must not pass.
- Real fresh-install/upgrade and network behavior checks remain pending until exercised.
  Preserve local diagnostics, privacy/security functionality, Sync and valuable user data.

No APK was available for this change. Thirteen synthetic parser/report tests passed;
these tests neither compile Android nor establish a successful stripped browser.
