# Shields groups and direct Dark Pages switch

The first card contains a direct site Dark Pages switch and Correct element colors.
The second contains trackers/ads, block element and clear blocked elements.
The third contains cookies and site-data shredding. Existing native actions remain intact.

The switch displays effective site policy (including inherited global default until
changed). Toggling sets an explicit ON/OFF override for the current origin/profile,
closes the popup and reloads to apply renderer policy and saved corrections together.
Private overrides retain their existing private-session scope. Corrections are disabled
and dimmed while OFF, with an entry-point policy check; no saved correction is deleted.
Native style gating is supplied by the companion correction-policy change.

Source composition and three-group regression tests pass. Android runtime layout,
actual switch tint and device behavior still need validation in the next APK.
