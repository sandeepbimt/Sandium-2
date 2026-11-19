# Frozen compact Shields implementation

Reference: approved compact v3; later owner correction determines order:
Ads and trackers, Dark pages, Cookies, Secure DNS.

- Legacy site header/master switch is hidden with its parent, not removed from
  Java state ownership. No Shields preference/default/backend logic is changed.
- Existing cookie/shred handlers now look through the common parent because
  their card is a sibling. Existing actions, menus and dark-toggle logic remain.
- Rows retain 48dp minimum touch targets with tighter vertical padding and faint
  dividers. Footer has no separate opaque band. DNS stays explicitly global,
  follows Cookies, and keeps provider management in Settings only.
- The panel uses the real packaged toolbar mark and the exact existing Balanced
  tracer class. Reduced-motion, attachment, focus and visibility handling are
  reused rather than a parallel animation implementation.
- Five details expose the shared outer rim. The first blocked-count tooltip
  gains a matching tapered body rim; native pointer geometry, copy and taps stay
  unchanged (the pointer itself is not separately outlined).
- Removed Manage-provider UI and its unused owned string. The shipping adapter's
  generated resource definitions and actual Java references are checked, and
  Settings source is checked byte-for-byte unchanged.

Validation: compact/group/DNS/rim focused checks and staged dark composition.
Exact pinned Brave popup/handler/assets were replayed through popup + dark +
element passes twice with identical output. Full Android build/render/lint is
not available locally; API-jar compilation test is skipped when SDK absent.

The added five detail reset inputs require a reset-only lint provenance update
when integrating. Historical unrelated aggregate failures are not suppressed.
