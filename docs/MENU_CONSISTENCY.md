# Menu consistency (held for next authorized run)

## Evidence

Reviewed four supplied screenshots and both supplied videos (155915/155916).
The sparse third quick page opens much shorter, then expands on swipe to page2.
Page1/page2 also shift slightly. This is content-dependent sheet measurement,
not merely the animation. Longer labels center the whole icon/text stack,
shifting icon baselines. All menu used a blue16sp button with a tiny Unicode
symbol; Desktop Off added a separate blue48dp button. A missing drawable also
added both a monogram and an empty image slot.

## Changes

* One sheet height from window/font configuration and the regular grid capacity,
  shared by quick pages, All menu, editor and native fallback. Width remains the
  existing window-derived width. More content scrolls inside this envelope.
* Full quick-page grid capacity reserved from first render, including sparse pages.
* Shared top-aligned tile geometry:26dp icon, fixed padding and label slot. The
  latter reserves two text lines and enough space for a separate48dp state action.
* Labels use12sp neutral text, consistent first baseline, maximum two lines and
  end ellipsis for unexpected long/localized actions. Full native action names
  remain accessible. No per-item font shrinking.
* Desktop state has its own single-line state action, preventing a long title
  from wrapping over and hiding On/Off. Native handler/enabled/checked semantics
  remain intact. Menu control labels are neutral, not blue.
* All menu uses a real drawn grid icon and the same tile/label metrics. Top-row
  icon accent remains; no icon colouring is removed from policy-required icons.
* Short resource labels:Private tab, Group tab, Reader, Translate, Install,
  Shred data, Add to home, Forward, Save page, Home. Static English Reload this
  page/Bookmark this page shorten to Reload/Bookmark; dynamic Stop/Edit bookmark
  titles and other locales remain untouched rather than mislabelling actions.
* Main header now displays Menu and Edit in the same48dp header used by All menu;
  editor Cancel/Done keep that envelope. Edit controls retain48dp touch targets.

## Verification and limits

Source contracts exercise configuration-only sizing, sparse grids, shared metrics,
neutral labels, state-slot dispatch and label resource coverage. Existing menu,
motion, theme and architecture tests also run. This is not an Android runtime
layout test. Next authorized APK must test swipe/Back/edit/cancel/save, All menu
scroll, disabled/managed actions, Desktop toggle, loading Stop/bookmark states,
large fonts, narrow/landscape windows, keyboard/TalkBack and reduced motion.
Very small windows intentionally scroll. Long labels intentionally ellipsize while
retaining the full accessibility name. No CI run or publication performed here.

Validation result:active283 (one pre-existing skip), Full49 and legacy19 passed;
menu-focused20, motion6 and native-theme17 passed. Full suite initially hit one
unrelated5s subprocess timeout in APK archive validation; unchanged Full49 rerun
passed. Independent source/API review cleared after the state-line, baseline and
dynamic-title safeguards above. No Android compilation/device render performed.
