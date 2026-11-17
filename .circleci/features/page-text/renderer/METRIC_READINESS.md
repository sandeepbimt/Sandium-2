> Historical blocker for the rejected custom FontBuilder multiplier. Current
> candidate instead uses existing native text-size-adjust CSS and leaves upstream
> font calculation unchanged. The broader idealized metric invariant is not
> claimed; see CSS_CANDIDATE.md. Both remain unactivated until validation.

# Text-size activation blocker

Status: **do not activate native scaling or its UI**. Saved/default settings remain
unchanged; no CircleCI application step was added. Source/model checks are not
full Chromium compilation or real rendering verification.

Exact Chromium revision: d331de35ca8ab1358c7a17e4bd41627d55eaef51.

## Confirmed boundary

Ordinary font-size px/em/rem/% uses specified parent/root font sizes. The proposed
FontBuilder multiplier acts on computed size, independently of existing native
accessibility scale. This does not prove correctness for font-metric units.

FontSizes::Ex/Ch/Ic/Cap and root variants in css_to_length_conversion_data.cc read
actual rendered font metrics. These already reflect the site factor. Reusing them
as font-size inputs can compound the factor. Compensation belongs only in the
font-size conversion context, never blanket ordinary geometry conversions.
Variable fonts, optical sizing, hinting, font-size-adjust and clamping still need
real-font tests; dividing metrics is not exact unscaled reference reconstruction.

## Rejected line-height heuristics

StyleBuilderConverter::ConvertLineHeight flattens authored percentages and calc
expressions into fixed Lengths using the already-scaled computed font size.
Authored fixed px lengths are also represented as fixed Lengths but have not
received the site factor. Therefore inspecting Length type cannot distinguish
whether font-size:1lh/1rlh already includes the factor. Dividing all fixed lengths
is wrong; dividing none is also wrong.

An alternative homogeneous line-height zoom requires more than changing that
converter. CSSLengthInterpolationType::ApplyStandardPropertyValue uses effective
zoom, and LengthPropertyFunctions::SetLength directly calls SetLineHeight for
fixed values. Underlying/inherited interpolation conversions remove only effective
zoom. Serialization and animation round trips must share a new convention.

Independent reviewer reproduced both issues. The attempted heuristic compensation
was removed from the candidate patch application, not silently shipped.

## Completion gate

A provenance-preserving unscaled font/line-height reference must cover initial,
inherited, percentage/calc, variable font/font-size-adjust, animated, reverted,
and root cases, including CSSOM/animation round trips. Alternatively a coherent
native text-zoom design must cover those same paths. Neither is complete here.

Require real Blink tests across px/em/rem/%/ex/ch/ic/cap/lh/rlh, nested/animated
values, text-scale meta, native accessibility and page zoom, ordinary and OOPIF
frames. Then compile Android and measure fresh load, BFCache Back/forward,
scroll position and layout-shift behavior. Default100/Off must match baseline.

`test_known_metric_blockers.py` records arithmetic counterexamples only. Passing
it verifies that the reasons to hold remain documented, not that rendering is fixed.

## Explored alternatives and concrete follow-up

The existing LocalFrame TextZoomFactor is not a shortcut: FontBuilder applies it
while FontSizes divides actual glyph metrics by effective zoom only. It shares
the source-derived metric-input compounding issue. Meta text-scale pages force
TextZoomFactor to1, and its live setter invalidates descendant layout. Existing
page zoom intentionally scales full geometry and is not this font-only control.

A possible implementation uses the supported css_properties.json5
computed_style_custom_functions setter/resetter hooks for line-height and a
paired inherited baseline Length in computed_style_extra_fields.json5. Baseline
state must participate in equality/cache identity. Initial/inherit/value must set
both channels; ambiguous SetLineHeight(Length) callers should fail compilation
until their semantics are assigned. A setter that merely marks baseline unknown
is not sufficient for later font-size:1lh.

Animation needs dedicated line-height interpolation: an InterpolableList of
actual and baseline InterpolableLength values, not a baseline hidden in
NonInterpolableValue. Cover neutral, initial, inherited, value, underlying,
merge/add/composite and apply in both channels. Parent conversion checkers must
compare both. Number interpolation atomically stores unitless percent markers
for both, evaluated against their corresponding reference fonts. Existing
always-invalidate behavior for additive conversion must remain.

For glyph units, retain pre-site font computation before clamp/size-adjust and
construct/cache the matching baseline font only where font-size metric inputs
need it. A scaled font description divided by the factor is insufficient where
clamping or variable-font size adjustment is nonlinear. FontSizeStyle references
must carry the correct baseline font and line-height for both parent and root.

These are design findings, not implemented changes. Full compilation must
identify every direct setter/serialization path and real renderer tests must
verify the design before enabling it.
