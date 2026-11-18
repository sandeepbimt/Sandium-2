# Navigation customization audit, 2026-11-18

## Scope and provenance

Diagnostic source revision `122430224fb8ea95a7669f987087eda72ce43e77`
was verified through GitHub. Its ordinary-transition, native-blur, Back-transition,
and base blur overlay blob hashes match the inspected files. Chromium pin:
`d331de35ca8ab1358c7a17e4bd41627d55eaef51`; Brave pin:
`44a84b1f89d9a35287289d6a3d493e362f5a5123`.
The reversible native-navigation comparison profile was OFF. This isolated audit
starts from `16be3ea`, preserving existing release branches and Raw Sandium.

## Changes versus pinned sources

- Sandium explicitly disables ordinary blur for Default; Low/Medium/High enable
  it and configure strength and hold/fade times. New recording timing matches
  High (675ms hold,300ms fade), but preference value was not exported.
- Adds optional darken layer and destination-policy fallback color selection.
- Captures native homepage pixels for ordinary transitions; preserves documented
  top-controls padding compensation. Does not use a hidden web surface as home.
- Attempts native history capture before checking renderer surface availability.
- Back cache miss uses outgoing blurred content rather than solid/favicon UX;
  if no safe source exists, falls back to ordinary history navigation.
- Changes slim compositor occlusion propagation for translucent render passes.
- Bypasses feed-restoration wait when feed is disabled.
- Restores upstream controls-SHOWN gesture ordering, reversing an older custom
  suppression. The older suppressed-controls path is NOT the tested behavior.
- Native wallpaper/layout, toolbar and insets remain interacting customization
  owners requiring runtime coordinate validation.

## Evidence and implemented lifetime repair

New recording: commit at4.777s, timeout5.440s, fallback shown5.765s,
paint receipt9.739s, fadeout9.741s. The solid fallback state therefore lasts
3.976s. The timeout-to-fallback mechanism exists in pinned Chromium; Sandium
extends/configures it, rather than originating the whole state machine.

The timer previously reset navigation/RFH ownership while visual layers and input
suppression remained alive. Consequently a later uncommitted finish could no
longer match `DidFinishNavigation` cleanup. The patch retains ownership across
the fallback phase. Paint can reveal only while a tracked navigation exists and
the current primary RFH matches its target. Normal exit/interrupt still retires
ownership. Timeout remains observable through existing timeout diagnostics;
terminal exit metrics now describe the terminal event rather than discarding
ownership at timeout.

This is NOT document-generation matching: same-RFH reuse can still need stronger
identity. It is NOT a compositor activation integration, a cure for the long
paint delay, or proof of eliminating flashes. No timings or visual defaults were
changed. No guessed offset, longer timeout, or indefinite retained overlay added.

## Native homepage jump: not fixed by the ordinary-blur patch

Return home: invoked12.582s, commit12.703s, paint12.780s, native shown13.040509s,
animation finished13.041256s. Native destination crossfade completion belongs to
the embedder; a renderer first-frame completion helper is not proof of native
view draw readiness. Captures at4.700/4.752s show outgoing native Y=-48px and
web Y=0 but detached. They do NOT measure restored homepage position at13.041s.
No full transforms or controls offset events prove a48px correction. User's
observed jump is real feedback, not disproved by those incomplete measurements.

Next: compare screenshot and live native view bounds/insets/composed transforms
at reveal; inspect wallpaper wrapper and toolbar ownership. Ensure destination
layout/draw and native-content-shown describe the same viewport. Preserve visuals.

## Verification / limitations

- Native blur source:7 tests passed (including pinned transform replay).
- Lifetime:2 tests passed; host C++ executes exact transformed timer, finish and
  paint methods with collaborator stubs, covering timeout then abort, unrelated
  abort, wrong RFH paint, correct RFH paint and duplicate late paint.
- Native transition diagnostics:4 tests passed (composition/replay).
- Back transition:9 tests passed.
- Full transition overlay script tests passed.

Not performed: complete Chromium compile, device rendering validation, real
compositor presentation test, CI build. Stub collaborators do not validate GPU,
Android lifecycle or final input-scope disposal. No release/pipeline was run.

## Release gate and continued investigation

This audit is not ready to be described as a complete navigation fix. The
four-second fallback and native-home movement remain separate unresolved UX
problems. An existing low-risk isolation axis is Default (ordinary blur disabled)
versus High, with wallpaper/address styling unchanged. Capture itself took tens
of milliseconds here, not the five-second commit-to-paint gap. Individual ad
request decisions do not prove the page's critical path; missing resource-to-
document and compositor-present linkage prevents attributing that gap.

A production handoff redesign needs destination-document identity, readiness of
its matching compositor frame (native draw for home), and bounded cleanup across
interrupt/error/detach. Do not simply expose the destination on commit, retain
outgoing pixels indefinitely, lengthen hold time, or introduce a guessed offset.
The exact isolated repair must be integrated onto the coordinated current release
base before a build; this audit branch does not include subsequent unrelated work.
