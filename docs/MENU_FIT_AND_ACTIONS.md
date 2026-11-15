# Menu fit and action availability

## Screenshot evidence

155540/155544/155548 show Sandium menu/editor over the internal homepage.
Exit is present in Available actions, not missing. The last customizable page
contains only Reload and large empty space.155551 is an Edge editor reference;
its browser-specific actions are not evidence those features exist in Sandium.

## Layout corrections

* Fix another plain View/WRAP_CONTENT height error, this time sparse grid fillers.
  Empty cells now have explicit 1px height and retain their horizontal weight.
* Replace fixed 410dp menu/88%-screen editor sizing with measured header+body
  intrinsic height at actual popup width, capped to available display height.
  This fits ordinary pages without vertical scrolling instead of merely hiding
  a scrollbar. Large fonts, small windows or many available actions still scroll.
* Put edit add/remove controls in a 48dp corner overlay rather than adding a 48dp
  row beneath every item. Native tap/drag/edit actions and accessible names remain.
  Icon content receives extra top spacing; no target is made smaller.
* Preserve page transitions, sparse-page minimum height, grouped surfaces and
  native conditional-action fallback.

## Homepage versus Android launcher

Earlier Add to Sandium home was inserted only into Brave's separate
buildPageActionsModelList customization catalog. It was absent from actual
buildMenuModelList. Insert the guarded model into the real PAGE_MENU as well,
with explicit label Add to Sandium homepage. On internal/private pages it remains
customizable but disabled. The action handler independently rejects null,
incognito and non-HTTP(S) tabs, and uses existing native profile custom links.
It is distinct from Android launcher installation or creating a phone shortcut.

Install/Create shortcut and other native page actions remain native/contextual.
The pinned Brave universal-install catalog checks
WebappsUtils.isAddToHomeIntentSupported(). Native menu availability also depends
on page/launcher capability. Do not manufacture a clickable install action for
an internal homepage, override policy, or restore stripped components just to
imitate Edge. User ordering remembers absent entries for later eligible pages.
Exit's existing native confirmation is unchanged; adding it from Available
makes it visible in the chosen position.

## Validation and limits

Three targeted source tests, 8 toolbar contracts, 6 motion tests, pinned menu and
home transformation/idempotence tests passed. Full pinned UI/removal composition,
reset/replay, interruption and bad-patch preflight passed. Independent review cleared; device validation remains required. No Android build or runtime measurement performed here.
Device tests: normal-font page/editor fit; sparse second page; large font and
landscape scrolling; all drag targets including new corner controls; cancel/save;
Add to Sandium homepage on normal HTTPS, duplicate and private/internal cases;
Android install/create shortcut on an eligible site and supported launcher.

## Initial opening fade

The initial render intentionally skipped the existing edit/page content fade
because mRenderedScreen starts at -1. Opening instead relied only on a native
PopupWindow animation style, whose actual OEM presentation was not established.
The user reports abrupt opening. Own the opening at the view attachment boundary:
a 100ms linear alpha fade over the complete sheet, set before its first draw.
No translation/scale or delayed interaction. Disable the custom window's extra
style so there is only one entrance effect. Existing edit and page motion remains.
System disabled animations and the existing low-end-device policy skip the fade.
Detachment cancels and restores alpha; stale completion cannot alter a newer run.
Six motion contracts and pinned menu source tests pass; device smoothness remains
unverified. No build started from this worker.
The window style change also means no window-level dismissal fade; this patch
addresses opening only and preserves immediate native dismissal semantics.
Independent review and full pinned composition/reset/replay passed.

## Leaving fade follow-up (supersedes immediate-exit limitation above)

Keep view-owned 100ms entrance, but configure an 80ms native PopupWindow exit
Fade.OUT transition. setEnterTransition(null) avoids a second entrance. Framework
PopupWindow handles its Back/outside-tap/action and lifecycle dismissals; no
custom wait, dismiss interception, delayed click or deferred cleanup callback is
added. Disabled system animations and low-end devices receive null transition.
The native API has existed since Android 23, below this pinned Android floor:
https://developer.android.com/reference/android/widget/PopupWindow#setExitTransition(android.transition.Transition)
Six motion and pinned menu source contracts pass. Device QA remains necessary
for rapid open/close, outside tap, Back, Settings action, rotation/background and
reduced motion; lifecycle teardown may legitimately skip visual animation.
