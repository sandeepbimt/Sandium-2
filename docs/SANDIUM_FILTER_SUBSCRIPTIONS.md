# Sandium native uBlock-compatible filter subscriptions

Sandium uses Brave's existing native custom-filter subscription engine for the
selected lists below. Each source remains hosted by its maintainer and Sandium
subscribes directly to its HTTPS URL. Filter-list bytes are downloaded from their maintainers through Brave's native subscription manager. The APK does not currently bundle a static offline snapshot.

## Selected list set

The 30 distinct URLs correspond to the selected checked entries in the supplied
uBlock Origin screenshot. The duplicate uBlock Cookie Notices row in uBO's
grouped view resolves to one unique URL and is subscribed once.

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

- On first opening Content Filtering, Sandium creates each missing subscription
  in Brave's native subscription manager. Existing matching subscriptions are
  adopted without changing their enabled/disabled state.
- New lists added by a later Sandium release are seeded once. A user's deleted
  list is not silently re-added on the next visit. Users can still add it again
  through Brave's normal “Add custom filter list” action.
- All 30 selected lists are enabled by default. A one-time migration re-enables the five additions that an earlier Sandium build incorrectly seeded as disabled; later user toggle choices are preserved.
- The native subscription manager seeds missing URLs during ad-block service startup, before normal browsing. New subscriptions immediately request high-priority downloads from their original HTTPS sources.
- The Content Filters screen retains per-list toggles and deletion, and exposes a **Refresh filters** action for enabled URL subscriptions.
- Brave's native subscription manager downloads the public URL directly and
  automatically refreshes active subscriptions using each list's Expires
  metadata, or its seven-day default when the list has no expiry metadata. The
  manual refresh action schedules high-priority downloads without invoking the
  unrelated Brave component-catalogue updater. The
  manual refresh action schedules high-priority downloads without invoking the
  unrelated Brave component-catalogue updater.
- The filter screen's Brave component-catalogue rows are not used for this list set. This means these subscriptions do not
  depend on Brave's private component updater, component catalogue, or
  Brave Services key.

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

- Brave Core pin: `v1.98.62` (`44a84b1f89d9a35287289d6a3d493e362f5a5123`).
- The implementation is a pinned Android Java/UI change and is intended for
  Fast Mode; no Full Mode Chromium rebuild is required by design.
- CircleCI no longer requires `BRAVE_SERVICES_KEY`; BuildBuddy credentials
  remain a separate remote-execution requirement.
- The lightweight CI test validates the 30 unique URLs, user-delete behavior,
  all-enabled defaults, friendly display names, and idempotent source
  transformation. Runtime enforcement still requires a built APK and device
  verification.

The filter sources remain owned and updated by their respective maintainers.


## First-launch timing boundary

The ad-block service creates missing subscriptions during profile startup and requests high-priority downloads before normal browsing starts. The engine can enforce each list only after its source download succeeds and its cached file is loaded; slow, blocked or offline networks can delay that first successful load. The APK does not yet contain a bundled offline snapshot. A guaranteed offline/instant first-page baseline would require a separately maintained APK snapshot followed by background source updates.


## Cache metadata and first-launch boundary

Each row displays the last update status/time already recorded by Brave, the cached list file size in MiB, and the number of non-empty, non-comment source entries in the downloaded text file. This is a source-entry count, not a count of the engine's optimized internal matcher records.

The ad-block service creates missing subscriptions during profile startup and requests high-priority downloads. The engine can enforce a list only after its source download succeeds and the cache file is loaded; slow, blocked or offline networks can delay the first successful load. A guaranteed offline/instant first-page baseline would require a bundled rules snapshot in the APK followed by background source updates.
