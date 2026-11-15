# Brave outbound UI link audit (2026-11-15)

Base: Sandium #1175 `51feb9da1fe4f14492c10b1b365fc16d54673b63`.
Pinned Brave source inspected: `44a84b1f89d9a35287289d6a3d493e362f5a5123`.

## Verified screenshot targets and implemented changes

- Main Settings and Shields/Privacy Settings question-mark menu: remove general
  targeted, site-settings and editor help menu items after `super.onPreparePanel`, not before fragment
  providers populate the menu. Runs on every preparation, including submenu traversal.
- WebRTC IP policy Learn more: hide the text and clear its click listener. Keep all
  four policy radio controls, their selection and persistence code unchanged.
- Background images sponsored content Learn more: hide that preference.
- Strict-cookie warning: retain warning wording and red emphasis; replace only its
  outbound clickable span with a non-clickable style span.
- Custom filter syntax summary: retain textual guidance; omit outbound link span
  and movement handler. Filter editor/save and engine remain unchanged.

The standalone overlay is `.circleci/scripts/apply-sandium-ui-links.py --core CORE --src SRC`.
It must run after source reset and existing UI/theme patches; repeat application
is idempotent and expected source drift fails closed. Integration must register all
seven `PATHS` plus Chromium `CONNECTION` for pinned-source reset. No build or publication is part of this patch.

## Extended pinned UI audit

Also removed:

- Chromium connection-information external help row (which Brave redirects to
  support.brave.app). Certificate details, warning descriptions and reset-certificate
  decisions remain intact. The native callback remains callable but emits no help row.
- Japanese onboarding completion/close redirect to Brave's tutorial site. Onboarding
  close/next behavior remains; it no longer opens an unsolicited product webpage.
- Brave-release promotional notification, whose sole action opens its support page.
  This does not change website/download/security notification channels.

Exact Chromium revision `d331de35ca8ab1358c7a17e4bd41627d55eaef51` was inspected
for SettingsActivity, SettingsMenuHelper, ConnectionInfoView and safe-browsing
settings. SettingsMenuHelper confirms the four help IDs. SettingsActivity updates
search help visibility *after* super.onPreparePanel; our subclass filters after
that completes. Enhanced Protection's inline explanation targets Google, not Brave,
and is deliberately unchanged.

### Classified residual source occurrences

- `feedback/BraveHelpAndFeedbackLauncherImpl.java`: implementation remains, while
  the audited Settings menu entry points are removed. Other callers may exist in
  Chromium surfaces outside the fetched files; no dead stub or global URL block
  is used to hide that audit limitation.
- `BraveActivity.java`/`BraveIntentHandler.java`: support URL remapping remains, but
  the audited connection-information help row is removed. Arbitrary user browsing
  and intents are not blocked or rewritten by this patch.
- Rewards/News/VPN/Wallet/Origin/Leo notifications/support/account URLs survive in
  excluded source groups. Prior removal pipeline owns their reachability; source
  strings alone do not prove a reachable APK UI.
- `RateFeedbackUtils` is a feedback API endpoint, not a UI hyperlink, and unchanged.
- Search-banner/provider traffic is managed by existing search-provider removals,
  not a new network block.
- Privacy-policy/terms/license attribution remains separate from promotional/help
  affordances. Retain legally required notices; this patch invents no Sandium policy
  URL and removes no license texts. A product-specific replacement needs legal/content
  review and the actual Sandium privacy policy, not an empty or misleading link.

This covers the screenshot surfaces and the directly identified reachable Java
support/tutorial links, not a proof that every possible Chromium/WebUI surface or
locale has no Brave link. Device coverage and wider compiled-APK UI crawling remain
necessary for an exhaustive product-wide claim.

Endpoint strings, user-entered websites, bookmark links, Safe Browsing/adblock
updates, search traffic and feature operation are expressly outside this UI-link
removal. The audit does not equate a Brave domain occurrence with a removable link.

## Validation and limits

`test-sandium-ui-links.py --core CORE --src SRC` replays onto copies of real pinned files,
checks idempotence, source-drift rejection, removal anchors and retained policy/
filter controls. Python compilation passes. No Android compilation, menu inflation
instrumentation, accessibility or device test has been performed. Verify both
Settings screenshots and WebRTC on device, plus strict cookies and custom filter
editing, after integration. Do not report exhaustive all-UI removal without the wider
Chromium/WebUI and legal review described above.

### #1179 ErrorProne correction

The first Android build caught dead private support state left by the no-op
connection-info callback: unused launcher, HELP_URL, mMoreInfoLink and linkText.
The follow-up removes the unreachable support launcher and its imports/state,
including mLinkUrl/TAG, rather than disabling warnings. The native callback keeps
its String signature with the explicit `unusedLinkText` name; ErrorProne recognizes
unused-prefixed parameters. Certificate and reset decisions remain unchanged.
Tests now cover pristine source, upgrading the old no-op, idempotence, leftover
identifier assertions and launcher body drift. Full ErrorProne/Android rerun still
required; source replay alone is not a successful build.
