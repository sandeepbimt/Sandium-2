# Sand-gold interactive accents

User feedback after installing #1148: welcome switches looked black/gray and their state was difficult to notice. Inspected the supplied screenshot (155259.jpg): black page, charcoal cards, very dark thumbs over gray tracks. This change preserves the neutral surfaces, ordinary white/gray text, Sandium logo and tracer, and semantic readiness/blocked-count colors.

## Palette and scope

- Dark interactive accent: light sand gold `#E8D3A2`.
- On-accent text: warm near-black `#292211`.
- Light-theme interactive accent: deeper gold `#6F561E`, rather than unreadable pale gold on white.
- Welcome checked switch: gold thumb with deeper gold track. Android may alpha-blend the track; the opaque gold thumb still visibly communicates ON. OFF and disabled controls remain neutral, and state position is unchanged.
- Welcome start button, radios/selector/restart hints and other existing primary-accent uses share the same color. Native primary/control/link tokens and menu action controls share the palette. Ordinary body text and menu item labels remain neutral.
- Explicit Android dynamic-color preference is preserved and may override native baseline tokens. This is not a promise to recolor system-owned UI or website contents.

## Evidence and limits

Contrast ratios: gold/charcoal 10.94:1; on-accent/gold 10.72:1; gold/deep-gold switch pair 4.72:1; light accent/lightest tested gray surface 5.66:1. Native theme tests cover 11 cases including resource closure, contrast, no semantic/error/private token scope expansion, and existing dynamic preference preservation. Welcome transformation/readiness tests, menu transformation/idempotency, motion tests and UI product gate pass. Native theme apply/reapply against pinned-source fixture is idempotent.

These are source and contrast checks, not Android rendering or runtime verification. Actual device check must confirm ON/OFF/disabled switches, light and dark Settings, Shields, menu/edit buttons, welcome start/restart, and unchanged green Shields logo/semantic counts after the crash fix is integrated and the APK compiled.
