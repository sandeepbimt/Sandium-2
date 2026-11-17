# Light-to-dark Back: destination temporarily renders light

## Evidence

Recording Library `libfile_8066a3f66f3c8191a26a89f16f8e9a3a`, 156053.mp4,
SHA256 1dc2c04d004a71ed1d8d88d01b914be9e3e6b326ada55c79c5de4cf81d44ff85.
Decoded every source frame (variable timestamps, no fixed-FPS sampling):

- Through frame110: light LiveLaw outgoing document.
- Frame111, 1.750844s: dark Google destination, potentially cached preview.
- Frame128, 1.937578s: Google itself renders light. Its actual cards, headings,
  search field and page background change, while layout/content remain Google.
- Frame137, 2.081122s: Google dark again. Light interval ~144ms.

This is not evidence for a flat white fallback or outgoing LiveLaw blurred cover.
A dark screenshot handed off to incorrectly light live destination and then corrected
is consistent with the pixels, but requires trace corroboration.

## Concrete overwrite surface

`renderer/patches.json` adds destination policy to ordinary commit, BFCache
PageRestoreParams and prerender activation. However `WebViewImpl::ApplyWebPreferences`
unconditionally reapplies `prefs.sandium_dark_page_flags` with no document identity.
`ApplySandiumCommittedDarkPolicy` resolves primary committed frame; a mismatched
SiteInstance returns -1. Preference changes during transition can therefore be
unmanaged or refer to a different document from the renderer receiving them.

`test_policy_handoff_ordering.py` compiles actual activation and setter blocks and
shows both ON destination overwritten by stale OFF and OFF overwritten by stale ON,
plus unmanaged overwrite. Later correct refresh repairs both. This is an artificial
ordering characterization, NOT proof that real Chromium sends this sequence.

## Diagnostic-only candidate

Adds flag-only navigation trace points at preferences, normal commit and BFCache
apply. No URLs/pixels/policy changes, no arbitrary delay, no forced global darkness.
Combine these with existing Back preview selection/handoff traces on Android15:

1. Google ON → LiveLaw OFF → predictive Back completed/canceled.
2. Reverse direction with destination OFF.
3. Warm BFCache restore; evicted/reloaded history; cold restore after relaunch.
4. Repeat10 times, slow/fast gestures; toolbar visible/hidden independently.
5. Change destination site's preference while it is cached; verify restored policy.
6. Frame capture must show zero wrong-theme destination frames, not merely a darker
   blank cover. Confirm scroll/layout unchanged and site OFF remains genuinely OFF.

## Correction direction (not yet implemented)

If traces confirm stale preference overwrite, bind live policy updates to the
actual destination document identity (not pending/visible URL, and not just a
SiteInstance). Prefer browser-issued document identity/generation with late updates
ignored after commit/activation. Preserve explicit current-document live toggles,
same-origin distinct documents, BFCache, prerender, internal/unmanaged clearing and
remote-frame propagation. A URL-only filter is weaker and same-document history
URLs require care. Do NOT solve by refusing every later preference update, because
that breaks live settings; do NOT force ON for all transitions, because reverse and
per-site OFF would fail. Destination screenshot/fallback selection alone cannot
correct a visible destination's theme flip.

## Narrow no-update correction candidate

The preferences transport now distinguishes **unknown/nonmatching (-2)** from
**explicit unmanaged reset (-1)**. Browser policy lookup returns -2 when no client,
no committed frame, or a SiteInstance mismatch means it cannot authorize an update
for the target renderer. Renderer ignores that one value. A matched committed
internal/error/opaque document still returns -1, and matched eligible sites still
return OFF/ON. Defaults and Mojo decode preserve the distinction. Ordinary commit
and BFCache/prerender params retain their original explicit -1/0/1 semantics.

The extracted native test verifies ON and OFF restored pages survive unmatched
preferences, legitimate unmanaged reset clears both, live ON/OFF changes remain,
and all four preference values survive the actual decode expression. Renderer
patch suite and existing native helpers pass. This is a correction of a proven
source-level invalidation defect, **not a claim that this recording's race is
fully diagnosed or fixed**. A stale but matched ON/OFF preference can still win;
full identity/generation binding remains necessary if trace shows that path.
Remote-main/OOPIF pages receiving unmatched values preserve their existing
commit/activation policy rather than being force-cleared; live propagation and
navigation paint must still be verified on actual Chromium/Android.
