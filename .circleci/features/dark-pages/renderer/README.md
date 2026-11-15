# Experimental Dark Pages renderer transport

**Not integrated into the build. Not a completed Dark Pages feature.**

Pinned Chromium: `d331de35ca8ab1358c7a17e4bd41627d55eaef51` (156.0.8078.74).
Fixtures retain upstream BSD copyright/license notices. SHA256SUMS.json records
exact source bytes retrieved from the matching Chromium git revision.

## Implemented

`WebContentsThemeClient.sandiumDarkPageFlags(WebContents)` JNI int contract:
bit 0 enabled; bit 1 header contrast; bit 2 preserve images; bit 3 preserve CAPTCHA.
The matching Java method must be supplied by the policy owner. Native masks to
four known bits. The Android content browser client updates WebPreferences both
at initial construction and after navigation, includes the flags in the changed
predicate, transfers via mojo traits, and sets Blink per-page Settings. Generated
Settings invalidates color scheme/style/paint when changed. Defaults are zero.
The frame-aware raster image classifier returns Disabled before dark-image
classification when enabled+preserve-images is true. It does not decode pixels,
modify image contents, or change process-global runtime flags.

## Explicitly missing / integration gates

* Header and CAPTCHA bits currently have **no semantic paint consumers**. Do not
  expose them as functioning UI controls, or claim a complete feature.
* Raster helper coverage is not blanket protection for inline SVG, CSS filters,
  CSS backgrounds bypassing the helper, canvas, WebGL or subframe rendering.
* This does not implement the requested single Oppo webpage palette. Existing
  platform DarkModeFilter receives colors/rectangles, not the relevant element
  or origin. Replacing all dark colors with one color destroys surface/text and
  semantic contrast. Palette implementation requires frame/style-aware semantic
  color roles and cache identity, and must handle already-dark pages explicitly.
* Header-logo protection needs upstream element-aware classification and a
  conservative header/background contrast intervention, including SVG and
  transparent raster assets. Width/height alone is not reliable logo evidence.
* CAPTCHA protection needs independently classified frame/element boundaries,
  including cross-origin frames and challenge canvases. It must not depend on
  PRESERVE_IMAGES: these are independent user controls.
* Verify JNI policy reads the correct destination at navigation and refreshes
  WebPreferences after a Shield change. Current/outgoing URL is not sufficient.
* Register every changed source path in all reset inventories, compose with all
  existing overlays, regenerate JNI/mojo/Settings, and compile Android before
  enabling. This experimental patch is deliberately absent from CI wiring.

## Tests run

`python .circleci/features/dark-pages/renderer/test_renderer.py`: four tests.
Checks exact fixture hashes, complete application, idempotence, atomic preflight
on unsupported anchors, and enabled+preserve flag truth table. **These are
source-transformation tests, not a native compiler or runtime test.** No APK,
Chromium unit tests, device rendering, performance or screenshot tests run.

## Required renderer tests before completion

Navigation A->B->back, policy change while visible, normal/private profile
isolation, OOPIF challenge frames, photos vs transparent logos, raster/SVG/CSS
background/canvas, already-dark pages, colored semantics, keyboard/form/error
contrast, cached paints when policy changes, device reduced motion, and
first-paint/background consistency. Validate actual Hindu logo asset rather
than infer its type from a screenshot.

## Additional exact-pin semantic findings

`core/style/computed_style.h:2632`: `ForceDark()` returns
`DarkColorScheme() && ColorSchemeForced()`. Thus setting the force-dark preference
alone is not a uniform-palette implementation on author-dark pages.

`core/css/resolver/style_resolver.cc:1848-1878`: adjusted styles can be stored in
and recovered from the matched properties cache. Putting DOM-specific logo or
CAPTCHA detection in `AdjustComputedStyle` without a corresponding cache key can
leak an exemption to unrelated elements. `RunUncacheableStyleAdjustment` runs
after that cache branch, and also on the animated/alternate resolution paths;
this is the candidate for element-aware policy, with inherited explicit metadata
and mutation invalidation still necessary. Do not put a DOM scan in each paint.

`core/paint/image_painter.cc:261`, `svg_image_painter.cc:131`, and
`box_painter_base.cc:826,871,1113` call the image helper patched here. This improves
coverage beyond ordinary IMG, but **does not prove all paths**. Inline SVG uses
individual paint/color roles and needs independent protection and tests.

`platform/graphics/dark_mode_filter.cc:66-76` explicitly warns the main-thread
image filter path calls `AsSkBitmapForCurrentFrame` and synchronously decodes.
Logo intelligence must not add this operation to first-paint critical paths.

## Revised navigation contract

JNI now takes explicit `GURL documentUrl` in addition to WebContents. Browser
policy uses only the primary frame's committed URL, and only when its SiteInstance
is the exact requested instance, the origin is nonopaque, the document is not an
error document, and URL is HTTP(S). Absent client/ineligible context clears custom
flags; eligible explicit OFF overrides stock force-dark. Legacy Java force/night
callbacks are no longer intercepted. Five source tests pass, including assertions
for those gates; **not simulated or actual navigation lifecycle tests**.

Exact caller investigation: `content/browser/web_contents/web_contents_impl.cc`
invokes OverrideWebPreferencesAfterNavigation around8328 inside
DidFinishNavigation, after observer notification. This proves post-commit policy
refresh and includes BFCache activation resend, but **does not establish
pre-first-paint policy delivery**. Pre-first-paint would require separate
navigation commit parameters/renderer document policy, with per-document lifetime
and prerender/OOPIF treatment; a visible-URL shortcut is not acceptable.

## Latest reduced scope and palette draft

The latest owner request removes separate automatic logo/header, CAPTCHA and
image controls. Only bit0 remains meaningful; enabled pages preserve image-helper
pixels by default. Old descriptions above describe earlier experiments, not UI
requirements. Manual element correction is a separate integration dependency.

A **non-shipping** style-stage palette consumer now runs after uncacheable style
adjustment. It tracks an inherited known-dark-surface bit, maps opaque neutral
surfaces toward black/#1a1a1a, bounds colored surfaces while retaining hue, lifts
dark text on known-dark surfaces, and preserves already-light text/alpha. It
suppresses the stock second inversion. SVG, authored background images/gradients,
filters/backdrop filters and forced-colors accessibility mode are excluded.

The actual color helper compiles against a narrow Color API fake and passes
140608 sampled colors for bounds, repeat-application stability and alpha
preservation. The first test exposed non-idempotent pale-color mapping; corrected
before committing. These are algorithm tests, NOT Blink generated API/renderer
compilation or browser screenshot tests.

Remaining review blockers: inherited transformed text entering an excluded
image/gradient subtree can still lose original authored text color; semi-transparent
background composites are not normalized; manual exemption contract not yet
integrated; visited background/border and UA form control cases need audit. The
source hook is deliberately NOT production-enabled. A strict uniform appearance
on all arbitrary CSS pages is not established by this draft.

## Paint-only replacement (supersedes the style-color draft)

The earlier style-color mutation is removed. A boolean policy is attached after
uncacheable style resolution and carried through PaintAutoDarkMode into
GraphicsContext's per-draw colors/flags. Authored foreground/background/visited
colors are not mutated, so excluded descendants can retain original inherited
colors. Exclusions persist down subtrees; semi-transparent/unknown backgrounds,
images/gradients, SVG, filters and backdrop filters are excluded conservatively.
The root decision requires the actual styled element and non-pseudo style, and
never synthesizes CSS background colors. ViewPainter separately applies root
policy to the native canvas background. Printing and accessibility forced-colors
mode are excluded. Shader flags are preserved, not forced through the stock dark
filter. Six source tests plus native helper/color-model tests pass.

This remains a **draft, not production approved**. Outstanding: direct
AutoDarkMode callsites bypassing PaintAutoDarkMode require complete audit;
manual element selection/exemption integration; pre-first-paint document policy;
actual generated Blink/Android compile; rendering screenshots and visual/semantic
contrast tests. Do not describe source/model testing as device validation.

### Review corrections after paint-only draft

Border and selection have dedicated mappings, with native-model contrast tests:
opaque border vs #1a1a1a >=3:1, selection text >=4.5:1. Semi-transparent solid
backgrounds are transformed at paint time with alpha retained over mapped dark
parents, rather than exempting their text; tests cover101 alpha levels. Ordinary
filter wrappers no longer disable palette (fixing the concrete opacity(1) text
counterexample). Author color-altering CSS filters still run normally and require
visual/manual correction if they intentionally invert content.

The owner specifically chose manual correction rather than automatic logo
handling. Preserved transparent black SVG/logos over dark surfaces can require
that correction; pixel preservation alone is not a visibility promise. Image/
gradient background subtree compositing still needs visual validation, especially
partly-transparent backgrounds. Manual correction not implemented by this patch.

Read-only audit of the full exact-pinned core/paint directory finds ordinary text
(text_fragment_painter), borders, backgrounds, MathML and decorations use the
PaintAutoDarkMode wrapper. The direct SVG text constructor is in an SVG-excluded
path. This is source evidence, not a renderer coverage test; native themed controls
and paint code outside core/paint remain to audit.

### Selection minimum-text and border semantics follow-up

Selection background is now #173a5b, tested against the lowest retained foreground
#b4b4b4 as well as every sampled foreground result (>=4.5:1 opaque contrast).
Chromatic borders retain channel ordering/hue instead of becoming fixed gray;
neutral borders remain #707070. Tests assert opaque border contrast>=3:1 across
all140608 sampled input colors, and preserve red/green dominance. Authored alpha
is retained, so these opaque contrast guarantees do not apply to translucent or
disabled content; those remain visual validation cases.

## Ordinary navigation pre-document commit transport draft

A new embedder getter resolves the final browser-validated URL after redirects
into `CommitNavigationParams.sandium_dark_page_flags` (-1 unmanaged,0/1 explicit).
Only outermost HTTP(S), nonopaque, non-view-source normal commits request it.
RenderFrameImpl transfers it into WebNavigationParams without mutating WebSettings.
FrameLoader applies it only after successful old-document detachment and
provisional swap, and before constructing/installing the new document. A canceled
unload/swap never reaches this block. Only regular outermost commits mutate the
shared Page Settings; JavaScript/XSLT replacement and subframe commits do not.
The existing committed-document preference refresh remains for live policy updates.

Seven source tests include exact ordering/gates. A new native fake-lifecycle
harness compiles the actual FrameLoader block and tests cancellation, success,
OFF, unmanaged clear, JavaScript/XSLT and subframe preservation. This is **not an
actual Chromium navigation test or first-frame screenshot proof**.

Remaining activation gap: BFCache/prerender activation may reuse an existing
Document instead of this normal commit path; changed preferences are resent by
upstream DidFinishNavigation. Timing of that refresh relative to activation's
first frame still requires native integration tests/further transport. Initial
empty documents/synchronous synthetic navigations are not claimed fixed.

## Coherent native baseline and detached-document callback correction

The current policy representation is **-1 unmanaged,0 managed OFF,1 managed ON**
through preferences/settings and commit parameters (Java returns0/1 for eligible
explicit document URLs). Neither commit nor committed-refresh code changes native
force-dark or prefers-color-scheme. The uncacheable style hook suppresses stock
inversion for managed documents only; OFF clears custom palette, and unmanaged
retains untouched native behavior. This removes the earlier light-to-dark author
media-query transition and the managed-to-internal forced-dark baseline leak.

Exact callback audit: Page::SettingsChanged(kStyle) calls InitialStyleChanged,
kColorScheme calls Document::ColorSchemeChanged, and kPaint invalidates view paint.
FrameLoader's old Document remains present but Shutdown has detached its style
engine. It is inappropriate to send live-document notifications there. Added a
narrow generated SettingsBase::SetSandiumDarkPageFlagsForCommit setter that writes
only this field with no invalidation/delegate mutation. Only the after-detach,
before-install block calls it. Normal live updates keep Style/Paint invalidation;
ColorScheme invalidation is unnecessary and removed for this custom setting.

Executed actual pinned Chromium `make_settings.py` with the modified settings
JSON5/template using pinned pyjson5 and installed Jinja2. Generation succeeded;
verified generated storage name, -1 default, no-notification commit setter and
Style/Paint normal setter. This is a real code-generation check, **not compilation
of Blink or Android**. The full native harness/source tests also pass (8 source
cases plus compiled helper/lifecycle/palette models).

## Activation transport draft

BFCache restore and prerender activation now include a current policy field in
PageRestoreParams and PrerenderPageActivationParams. Browser-side owners resolve
it from the restored/activated main document's committed URL (not the address bar)
and distribute the same policy to every RenderView, including remote-frame views.
Opaque/error/non-HTTP documents remain unmanaged.

WebViewImpl applies it through the normal invalidating setter before BFCache
resume/visibility/pageshow or prerender state/events change. Unlike new-document
commit, these Documents are alive and need style/paint invalidation to discard
old paints. Native force-dark/preferred scheme remain untouched. Nine source
tests assert ordering and URL binding; actual activation blocks compile and pass
fake live-Settings/multiview tests. These are **not actual browser BFCache or
prerender rendering tests**. Generated Mojo/complete native compile, activation
races and first visible frame screenshots remain required before shipping.

## Manual element correction integration contract

Added inherited `SandiumManualColorOverride` metadata (defaultfalse, paint
invalidation). Manual owner's native registry Apply must run **after** the final
`ApplySandiumPaintPolicy(builder, element, element_or_pseudo_element, parent_style);`
line in RunUncacheableStyleAdjustment. For a real selected-node override it sets
manual=true, palette=false, ColorSchemeForced=false. Otherwise it must preserve
inherited manual state, not clear child exemptions. Undo invalidates the selected
subtree to regenerate state from the parent and native registry.

PaintAutoDarkMode explicitly returns Disabled for manual state, preventing both
custom palette and stock fallback. Image helper and ViewPainter root override also
respect it. Inherited manual state short-circuits the automatic style policy.
The native fake-API test compiles the actual paint wrapper for all8 combinations
of manual/custom/stock flags. Ten source tests and all native helper tests pass.
This is the renderer-side contract only; final manual registry/picker composition
and actual generated-field rendering tests remain required.

### Actual ComputedStyle generation and protected API correction

Ran exact-pinned make_computed_style_base.py against all pinned CSS inputs plus
modified extra fields. Generation succeeded and verifies inherited copies,
defaultfalse, public getters/setters and kPaint diffs for both metadata bits.
Inspecting the generated header exposed a real compile issue: BackgroundInternal
is protected on the builder, so a free helper cannot use it. Moved the policy
helper into StyleAdjuster, the existing declared friend of ComputedStyleBuilder,
and added its declaration to style_adjuster.h. A new test compiles the actual
helper against protected-access fake APIs and exercises root/pseudo/inheritance,
manual, managed/unmanaged, image/SVG, printing and forced-colors cases. This
strengthens source/type validation but still is not a full native Blink compile.

## #1179 generated storage correction (local only)
The two inherited paint-policy booleans lacked `field_group`, adding them to
ComputedStyleBase's hot root Data bitfields. Exact pinned generation shows root
bit count159→161, crossing a32-bit allocation boundary: compiled extracted actual
Data declarations measure20→24bytes. This explains the4-byte growth reported by
#1179's unchanged ComputedStyle size assertion (68 versus64).

Both booleans now use existing `field_group: "inherited"`, alongside upstream
InForcedColorsMode. They remain inherited, defaultfalse, paint-invalidating,
compared in inherited group equality, copied via the existing inherited group,
and set through generated copy-on-write Access. No size assertion is modified.
Exact regenerated root storage and Data declarations are byte-for-byte baseline
again; inherited group bit count15→17 fits its existing4-byte word. Root Data
measures20/24/20bytes (baseline/broken/fixed), inherited bitfields4/4/4.

Generation used the pinned make_computed_style_base.py with exact css_properties,
computed_style_field_aliases, runtime_enabled_features, css_value_keywords and
css_group_config inputs, varying only computed_style_extra_fields. Run
`check_generated_packing.py BASELINE_DIR BROKEN_DIR FIXED_DIR` on those generator
outputs to verify root-storage identity, generated setters/group equality and
compile their actual bitfield declarations. This is stronger than a hand-written
layout model but is NOT a full Chromium/Android compile: the actual unchanged
ComputedStyle assertion still requires the next authorized native build.
