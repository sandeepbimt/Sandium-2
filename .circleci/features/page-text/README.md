# Global webpage text candidate

Default: Website default(100%), Reader typography Off, justification Off. No
stylesheet or font override is installed at that default. Settings → Appearance
→ Webpage text is the only UI; there is no Shields row or per-site control.

## Current implementation

The slider changes a sample only. Save persists a global profile choice for the
next document; it never rewrites an open page, scroll event or restored cached
page. Normal settings use a registered non-sync profile preference. Private
changes stay in memory. Legacy site records are retained but ignored.

Nondefault size uses Chromium's established `text-size-adjust` percentage as a
native user-origin stylesheet before initial document style. FontBuilder and
line-height calculation are unchanged. The percentage replaces a site's own
text adjustment, not necessarily multiplying the currently displayed size. UI
labels this native adjustment and states that actual size/layout depends on the
site. It is not minimum-font-only, default-font-only or whole-page zoom.

Optional justification independently targets semantic article paragraphs with
conservative exclusions. No DOM detection pass, JavaScript injection, loading
wait, content hiding or scroll observer is introduced. Dynamic content uses the
ordinary CSS cascade. User rules can match shadow content, while article
selectors across shadow boundaries need renderer tests.

The browser captures the final-destination global policy and sends it before
fresh document creation. OOPIFs inherit the accepted owning Page snapshot, not
preferences changed after that Page loaded. Failed commits retain consistent
canonical and outgoing policies. HTTP(S) documents and parent-guarded embedded
about:blank/srcdoc are covered by the consumer. Newly initialized local roots
under remote parents may still have default policy before regular commit; no
late restyle is used to mask that edge. Internal/fenced/top-level about surfaces
are outside the ordinary webpage claim.

## Pinned, atomic composition

Chromium: d331de35ca8ab1358c7a17e4bd41627d55eaef51 (156.0.8078.74)
Brave: 44a84b1f89d9a35287289d6a3d493e362f5a5123

After complete Dark Pages/manual correction composition and its verification:

```sh
python3 .circleci/features/page-text/apply.py "$SRC" --repo "$ROOT"
python3 .circleci/features/page-text/apply.py "$SRC" --repo "$ROOT" --verify-only
```

Use this combined runner, not the three transforms separately. It stages Android
UI/JNI/prefs, native transport/style, then OOPIF composition. It validates all
outputs and complete replay before writing source files. Replay reverses only
exact owned OOPIF extensions in staging so the base native layer can reapply
safely. Source pin mismatch or a late anchor failure writes nothing.

`integration-plan.json` is the exhaustive reset/output inventory:
- Union `chromium_restore` into existing Chromium restore manifest.
- Union `core_restore` into Brave restore manifest (paths relative to src/brave).
- Union `generated_overwrite` into generated-output inventory (relative to src).
- Perform the existing canonical reset BEFORE Dark Pages and this composition.
- Run Dark Pages verification before this intentional overlay of shared anchors;
  run this combined verification after it. Final full-product reset/replay tests
  must include this order, not independently reapply dark-only patches last.

The module itself does not activate a pipeline or launch a build. The integration
owner must add the two commands and inventory to the shipping sequence, then run
its complete source/flow validation. Do not expose the UI without its consumer.

## Focused verification

```sh
bash .circleci/features/page-text/tests/run-tests.sh
JSON_JAVA_JAR=/path/to/json-20240303.jar bash .circleci/features/page-text/tests/run-profile-tests.sh
python3 .circleci/features/page-text/tests/test_ui_transform.py
python3 .circleci/features/page-text/renderer/test_native.py
python3 .circleci/features/page-text/renderer/test_native_api.py
python3 .circleci/features/page-text/renderer/test_brave_patch_replay.py
python3 .circleci/features/page-text/renderer/test_oopif.py
python3 .circleci/features/page-text/renderer/test_css_candidate.py
python3 .circleci/features/page-text/tests/test_combined.py
```

Passed:63 model/compiler assertions,49 actual-adapter serialization/JNI
assertions with mocked Chromium APIs,5 UI transform tests,9 native source tests,
10 OOPIF source/model tests,64-policy Java/native CSS parity,4 complete pinned
fixture composition/atomicity/readback tests. These are not Android compilation
or real renderer/device tests.

## Remaining validation and honest limits

Full Android compile, actual font/line-height rendering, native accessibility,
meta text-scale, shadow/iframe behavior, dynamic content, cold/warm navigation,
scroll/BFCache/Back/forward and default-versus-baseline filmstrips remain required.
Measure load time and layout shifts; do not promise zero cost or prevent website
layout changes. Fixed website containers can still overflow enlarged text.
A local desktop rendering probe was blocked by process/socket restrictions and
produced no rendering evidence.

`renderer/CSS_CANDIDATE.md` details current semantics. `METRIC_READINESS.md` and
`test_known_metric_blockers.py` preserve findings about the rejected custom
FontBuilder multiplier; that multiplier is NOT part of the current patches.

## Native API regression from build1311

The URL predicate uses exact pinned KURL::ProtocolIsInHttpFamily (Http casing).
The real pinned kurl.h is hash-recorded and the complete emitted embedded-URL
predicate is syntax-compiled against its extracted method declarations. This
catches the previous misspelling that string-only composition tests missed.
Canonical reset owns document.cc, so retry starts from upstream and reapplies
the corrected base and OOPIF layers rather than modifying prepared source in place.

## Pinned Brave replay regression from build1313

Raw Chromium reset must replay Brave's document.cc URL-rewrite hook and RFHI
isolation/nonce/window hooks before typography. The feature inventory lists all
six matching pinned Brave patches across its20 Chromium reset owners, and the
canonical recipe validates those mappings. Hash-recorded exact document/RFHI
patches are applied before full Dark Pages→typography composition in regression
tests. This restores the caller of RewriteBraveToChrome, not warning suppression.
