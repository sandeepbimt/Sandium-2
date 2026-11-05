# Sandium native uBlock-compatible filter subscriptions

Sandium uses Brave's existing native custom-filter subscription engine for the
selected lists below. Each source remains hosted by its maintainer and Sandium
subscribes directly to its HTTPS URL. Filter-list bytes are not mirrored in the
APK and are not downloaded from Brave's component catalogue.

## Selected list set

The 25 distinct enabled URLs correspond to the checked entries in the supplied
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
- Each subscription is initially enabled. Its normal Android toggle and delete
  controls remain available in the Content Filtering screen.
- Brave's native subscription manager downloads the public URL directly and
  automatically refreshes active subscriptions using each list's Expires
  metadata, or its seven-day default when the list has no expiry metadata.
- The filter screen's Brave component-catalogue rows and component-update
  action are not used for this list set. This means these subscriptions do not
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
- The lightweight CI test validates the 25 unique URLs, user-delete behavior,
  enabled-by-default seeding, friendly display names, and idempotent source
  transformation. Runtime enforcement still requires a built APK and device
  verification.

The filter sources remain owned and updated by their respective maintainers.
