# Build 1418 follow-up: Android acceptance checks

Use the same phone and URLs for both builds. Start with Low and app dark
mode on. Keep website settings, Shields, and network the same. When changing
blur or Darken, use the normal quick restart.

| Area | Exercise | Pass criterion |
| --- | --- | --- |
| White flash | Omnibox search; YouTube or Facebook homepage shortcut; ordinary in-page links (same host and cross-host); Back | No standalone white or light-grey loading frame between dark pages; no toolbar jump or change to scroll restore. |
| Page background | Dark app with site darkening off; light site with an undeclared root canvas; browser's light theme; slow load; canceled or failed load | Site text remains readable after the first paint. No stale dark canvas, including after cancel or renderer failure. |
| Shortcuts | Tap a tile that redirects slowly; cancel or go Back; long-press, reorder, and edit | Immediate native press feedback before the response starts, one direct navigation, existing address progress, unchanged editing. Time to response remains dependent on the site and network. |
| Blur | Test Off and Low after restart; compare Medium and High against Low on both quick and slow first paint | Off and Low keep stock timing; Medium and High do not alter the slow-load fallback or cause a missed first tap. Darken remains inactive with blur Off. |
| Popup surfaces | Open Shields, Menu, All Menu, and Edit on a black page; use outside tap, action and Back; disable animations | Subtle soft-grey outer edge only; Menu opens and closes like Shields; no change to internal paging, tap targets, or close order. |
| Dark surfaces | Compare Shields, Menu, Settings search, native Settings subpages, and Welcome | Matching dark outer surfaces and charcoal rounded cards; existing light and dynamic modes unchanged. |
| Justification preview | At 75% and 100%, toggle Justify and adjust slider in the Webpage text dialog | Wrapped lines reach both edges when checked, last line stays ragged, sample copy stays the same, no live webpage setting is applied until Save. |
| Autofill services | Fresh profile, upgrade with a provider already selected, cancel and accept restart, regular/private tabs | Built-in row absent and built-in filling Off. External switch defaults Off, remains on for existing valid opt-ins, and respects Android service selection. Saved credential data remains. |
| Secure DNS | Fresh app; choose Cloudflare from one surface and check the others; add/test/remove a custom HTTPS endpoint; turn Off; verify managed policy | Off on all three surfaces by default. One global selection, explicit provider secure mode, custom validation off the UI thread, and Android Private DNS untouched. No restart or delay to the resolver on unrelated UI interactions. |
| Welcome | Fresh profile; chooser centered; check narrow screen and large fonts; ordinary onboarding and restart | Labels remain readable and centered. No change to the welcome button or first homepage notification sequence. |

A passing APK compile is not proof that the flash is gone. Check the frame
sequence on the phone before promoting this candidate as a clean base.
