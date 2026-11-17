# Native transition ring producers (held candidate)

Requires the reviewed ContentBrowserClient diagnostics bridge and recorder events
21–23. `apply.py::plan(root)` returns changes without writing. It must run after
ordinary-transition, native-blur-source and predictive-Back product transforms.
Not wired to a build here. No animation decision, timer, offset or capture changes.

All payload work is behind the bridge's enabled/private gate. Native navigation
IDs are from NavigationHandle or the animator's tracked request; zero explicitly
means unlinked (before a request or after native reset). No URL, title, raw entry
identifier, pointer value or arbitrary string is recorded. Events observe current
synchronous state; they do not buffer a request-time payload for later delivery.
Accepted/mismatched frame callbacks use their activation_time. Other events use
TimeTicks at occurrence. Java receipt time must not be treated as this clock.

## Schema

21 BLUR_TRANSITION (8): stage, animation state enum, detail, has blur, has fallback,
blur width px, blur height px, delegate top height px.
Stages: 0 ready attempt (same-document1/BFCache2/reload4 flags), 1 source choice
(native pixels1/outgoing web2/valid surface4 flags), 2 state change, 3 exit(reason),
4 hold timeout. Enum values refer to the pinned native source.

22 PREDICTIVE_BACK (8): stage, animation state enum, navigation state enum, detail,
fallback, copied-from-native, screenshot width px, screenshot height px.
Stages: 0 selection(direction), 1 cancelled, 2 invoked, 3 native content shown,
4 first-frame timeout, 5 common completion helper, 6 tracked request(primary-main),
7 abort(reason), 8 state change, 9 accepted activation, 10 mismatched activation.
Stage5 alone is NOT evidence of an actual activated destination frame.

23 TRANSITION_LAYER (16): stage, depth, local x/y, width/height, transform identity,
opacity, has parent, delegate top height px, backing width/height px, DIP scale,
kind, ancestry truncated, reserved0.
Stages/kinds: 0 blur root insertion/0 unspecified source; 1 Back screenshot/3;
2 native blur pixel child before attachment/1; 3 Back native live clone/4.
Ancestry caps at16. Positions are LOCAL, not window coordinates. A nonidentity
transform requires additional matrix evidence; these rows cannot reconstruct it.

## Verification and limits

`python -m unittest discover -s tests -p test_native_transition_diagnostics.py`
checks full pinned/product source composition, replay, fail-closed anchors,
byte-exact reversal and compiles generated payload blocks with host collaborators
under C++17 -Wall -Werror. Disabled capture avoids payload dereferences, and depth
is bounded. This is not a Chromium native compile or device verification.

No Java capture result/epoch transport, renderer pipeline, matrix reconstruction,
or cross-layer request identity is supplied by this module. Ring admission and
session caps belong to the reviewed bridge/recorder. Existing upstream trace
categories may contain different data; this module makes no privacy claim about
an entire upstream trace export. Diagnostics identify evidence, not a navigation
fix or proof that the 112px discrepancy has been resolved.
