# #1173 display and tab badge correction

## Device evidence

Reviewed both owner attachments (15 November 2026): actual #1173 screenshot
shows `google.com/search?q=...` in the resting field and a detached plain plus
at the bottom-right of the tab count. Approved cropped reference instead shows
a blue circular plus overlapping the count outline at the upper-right.

## Root cause and bounded correction

The native pinned LocationBarModelImpl::GetURLForDisplay omits HTTPS and trivial
subdomains, while GetFormattedFullURL retains HTTPS. Our earlier Java guard
considered any display/edit difference a rewrite, returning before concise
formatting. Ordinary Google search therefore never reached the short display.

The correction admits only a display string exactly equal to Chromium's native
scheme/trivial-subdomain-omitted rendering of the same canonical GURL. Unknown
rewrites still take the native path. The native concise formatter then omits the
path/query, yielding `google.com`. No registrable-domain splitting, regex host
rewriting, hand-written IDN display, or editing-string truncation was added.
Meaningful subdomains, native spoof-safe IDN representation and ports remain.
Offline, frozen, publisher and special-page paths earlier in the method remain
untouched. Full native formatted URL remains editing text. Native formatter
mismatches conservatively retain native display rather than guessing identity.

Pinned primary source:
https://github.com/chromium/chromium/blob/d331de35ca8ab1358c7a17e4bd41627d55eaef51/components/omnibox/browser/location_bar_model_impl.cc

Badge drawing now uses a small light-blue circular backing at top-end with dark
plus. Native count/outline/notification drawable and both action listeners are
unchanged. RTL mirrors end placement; disabled alpha and shared canvas animation
path remain. There is no additional hit target or duplicate new-tab button.

## Verification and limits

11 unified address and 7 toolbar source/model tests pass. The decision-model
cases do not execute Chromium's JNI/native formatter. Android compilation,
real rendering, click/hold and native IDN/port formatting require later build and
device verification. No run or publication is authorized until owner confirms.
