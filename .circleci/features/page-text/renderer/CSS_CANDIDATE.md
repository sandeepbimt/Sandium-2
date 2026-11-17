# Native CSS text-size candidate (not activated)

Scope: Settings-only/global text-size slider and optional article justification.
Default100/TypographyOff is a true no-sheet/no-font-change path.

## Established engine path, exact pin

Chromium d331de35ca8ab1358c7a17e4bd41627d55eaef51:
- public/common/web_preferences/web_preferences.h enables text_size_adjust on Android.
- WebViewImpl applies this native setting, without changing our profile controls.
- FontBuilder already honors non-auto text-size-adjust independently of native
  TextZoomFactor, page effective zoom, minimum font sizes and font-size-adjust.
- StyleBuilderConverter::AdjustedZoomConversionData also honors it for line-height.
- This candidate does NOT patch FontBuilder or font/line-height computation.

Document::Initialize installs a native user-origin stylesheet before initial
StyleForViewport. No user-controlled strings are interpolated, just validated
integer75..150 step5. The consumer checks native GetTextSizeAdjustEnabled rather
than force-enabling it on unsupported/special surfaces. It includes both native
prefixed and standard aliases. At100 there is no size override, not a forced100%
that could change a site's existing text-adjust behavior.

## Meaning and limits

This is native text adjustment, not page zoom, default-font-only substitution,
minimum-font-only substitution, forced rem/px font sizes, or article-only sizing.
On nondefault selection the user sheet's !important declaration supersedes author
inline/stylesheet text-size-adjust on matching elements. A site's DOM scripts
cannot remove the native sheet as if it were a DOM style element. Scripts may
still change their own font/layout, canvas text, or alter their own layout. Native user-origin universal rules can also match
shadow elements; article descendant targeting across shadow boundaries still
requires renderer tests.

Native behavior is retained, including glyph-metric/line-height edge cases and
fixed-size website containers. We do not promise exact scalar multiplication of
every glyph or universal zero reflow. Percentage can replace a site's explicit
text adjustment; returning to Website default restores site behavior on reload.

Changes save globally for future documents; existing documents/BFCache pages do
not receive a late preference refresh. Fresh dynamically added matching content
receives normal CSS cascade, without whole-page JS rescans. Website-generated
content/font loads can independently cause shifts. Global policy does not mean
rewriting all open tabs immediately. Parent-guarded about:blank/srcdoc are included
for ordinary embedded documents. A new local root below a remote parent can have
default policy during initial-empty initialization before regular commit; this
edge remains unverified and is not repaired by a late restyle.

## Verification and remaining gate

- Source composition checks exact pin, atomic mismatch and repeated application.
- C++ extracted native CSS builder matches Java compiler for all64 valid packed
  combinations; default and unsupported platform skip scaling.
- Existing FontBuilder fixture remains byte-identical after composition.
- Global model/profile/UI tests pass independently of renderer behavior.
- OOPIF snapshots preserve accepted policy, including canonical failed commits.

An installed nearby desktop Chromium156.0.8078.79 probe was attempted, but the
execution environment denied process sockets even after escalation. It did not
produce rendering results and is not the pinned Android binary.

Before activation: Android compile; native/user-origin precedence and dynamic
content tests; exact font/line-height/site layouts; accessibility/meta-text-scale;
shadow/document/frame behavior; cold/warm navigation, scroll/BFCache and default
baseline comparison; verify no first-paint delay or late feature-induced shift.
