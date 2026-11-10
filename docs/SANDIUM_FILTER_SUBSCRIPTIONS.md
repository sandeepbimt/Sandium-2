# Sandium native uBlock-compatible filter subscriptions

Sandium uses Brave's existing native custom-filter subscription engine for the
selected lists below. Each source remains hosted by its maintainer and Sandium
subscribes directly to its HTTPS URL. Filter-list bytes are downloaded from
their maintainers through Brave's native subscription manager. The APK does not
currently bundle a static offline snapshot.

## Selected list set

The 29 distinct URLs correspond to Sandium's selected filter set. The duplicate
uBlock Cookie Notices row in uBO's grouped view resolves to one unique URL and
is subscribed once. The generic uBlock Annoyances list is deliberately excluded;
the overlapping EasyList and AdGuard annoyance lists remain selected.

| Group | Filter list |
|---|---|
| uBlock filters | uBlock filters – Ads |
| uBlock filters | uBlock filters – Privacy |
| uBlock filters | uBlock filters – Quick fixes |
| uBlock filters | uBlock filters – Unbreak |
| Ads | EasyList |
| Ads | AdGuard – Ads |
| Ads | AdGuard – Mobile Ads |
| Privacy | EasyPrivacy |
| Privacy | AdGuard/uBO – URL Tracking Protection |
| Malware domains | Online Malicious URL Blocklist |
| Malware domains | Phishing URL Blocklist |
| Multi-purpose | Peter Lowe’s Ad and tracking server list |
| Multi-purpose | Dan Pollock’s hosts file |
| Cookie notices | EasyList – Cookie Notices |
| Cookie notices | AdGuard – Cookie Notices |
| Cookie notices | uBlock filters – Cookie Notices |
| Social widgets | EasyList – Social Widgets |
| Social widgets | AdGuard – Social Widgets |
| Social widgets | Fanboy – Anti-Facebook |
| Annoyances | EasyList – AI Widgets |
| Annoyances | EasyList – Chat Widgets |
| Annoyances | EasyList – Newsletter Notices |
| Annoyances | EasyList – Notifications |
| Annoyances | EasyList – Other Annoyances |
| Regions/languages | IndianList |

The unchecked uBlock Badware Risks row and the personal “My filters” rules are
not included.

## Runtime behavior

- Sandium seeds missing URLs during native ad-block service startup, before
  normal browsing. Existing matching subscriptions are adopted without
  changing their enabled/disabled state.
- All 29 selected lists are enabled by default. A one-time migration re-enables
  the four retained AdGuard additions that an earlier Sandium build incorrectly
  seeded as disabled; later user toggle choices are preserved.
- The generic uBlock Annoyances subscription is removed at native startup from
  existing profiles, including both its legacy
  `uAssets/filters/annoyances.txt` URL and the expanded
  `uAssetsCDN/filters/annoyances.min.txt` URL. It is no longer in
  Sandium's selectable/default catalogue.
- New lists added by a later Sandium release are seeded once. A user's deleted
  list is not silently re-added on the next visit. Users can still add it again
  through Brave's normal “Add custom filter list” action.
- New subscriptions immediately request high-priority downloads from their
  original HTTPS sources. Brave subsequently refreshes active subscriptions
  using each list's Expires metadata, or its seven-day default when a list has
  no expiry metadata.
- After the default subscriptions are registered, Sandium issues one native
  additional-engine provider notification. This follows the same provider
  observer → filter-set build → resource load path reached when a user
  re-enables a subscription, and bypasses Brave's one-time DAT-cache startup
  notification suppression. It does not toggle a filter or modify any
  subscription's enabled preference.
- Successful download completion continues to notify the native provider so
  newly downloaded source content is loaded. The reload-generation guard keeps
  an older, slower aggregation from overwriting a newer filter set.
- The Content Filters screen retains per-list toggles and deletion, and exposes
  a **Refresh filters** action for enabled URL subscriptions. Manual refresh
  schedules high-priority downloads without invoking Brave's unrelated
  component-catalogue updater.
- The filter screen's Brave component-catalogue rows are not used for this list
  set. These subscriptions do not depend on Brave's private component updater,
  component catalogue, or Brave Services key.

## Compatibility boundaries

The rules are processed by Brave's native adblock-rust engine, not by the uBlock
Origin extension. Brave documents broad compatibility with uBlock Origin's
static filter syntax, but not a promise that every advanced uBO-specific
feature is identical. In particular, advanced cosmetic/scriptlet behavior and
new syntax must be validated against the pinned engine version and real pages.
A successful download alone is not proof that every rule in a list is enforced.

Because this configuration enables many overlapping lists, test for duplicate
rules, false positives, page breakage, battery/network use, and rule-count
changes. Users can disable or remove individual lists in the filter screen.

## Build and verification

- Brave Core pin: `v1.98.62`
  (`44a84b1f89d9a35287289d6a3d493e362f5a5123`).
- The native engine activation is a C++ change and is routed through the
  Sandium Full Mode staged build on the feature branch. The build must produce
  an optimized ARM64 Release APK.
- Full Mode retains the existing Siso/BuildBuddy remote-execution settings and
  canonical reference restore; it must not replace the protected
  `3c8004b` / CircleCI cache-job-`949` checkpoint.
- CircleCI no longer requires `BRAVE_SERVICES_KEY`; BuildBuddy credentials
  remain a separate remote-execution requirement.
- Offline patcher tests verify subscription catalogue integrity, user-delete
  behavior, idempotent source transformations, and native startup activation
  ordering. Runtime enforcement still requires a built APK and clean-profile
  device verification.

The filter sources remain owned and updated by their respective maintainers.

## First-launch timing boundary

The native engine activation runs during service startup, after Sandium's
subscription providers are registered. This ensures the current provider set is
announced to Brave's additional ad-block engine instead of relying on the
first-change notification that DAT-cache startup optimization may consume.

Activation does not make remote downloads synchronous and does not create
filter data that is absent from the profile cache. On a genuinely fresh
installation, the subscription manager starts high-priority downloads, and
each successful download triggers another native provider reload. Until a
source's first successful download completes, its rules may not yet be
available to block the first page. Network delay or offline installation can
therefore delay full filter coverage. A guaranteed offline first-page baseline
would require a separately maintained filter snapshot bundled in the APK and
updated in the background; that is not part of this change.

## Cache metadata

Each row displays the last update status/time already recorded by Brave, the
cached list file size in MiB, and the number of non-empty, non-comment source
entries in the downloaded text file. This is a source-entry count, not a count
of the engine's optimized internal matcher records.
