# Four blur choices, #1418 follow-up (local candidate)

Off disables the native blur feature. Low enables its stock 150ms fade,350ms
hold and sigma3. Medium/High opt into175/200ms only for final fade when a blur
surface remains and fallback opacity is zero. This is a candidate timing choice,
NOT device-validated smoothing or a stronger sigma setting. Restart required.

A separate named feature controls reveal duration. The upstream fade parameter
is deliberately NOT overridden, because it also controls fade-to-fallback.
Fallback blend and fallback-only reveal remain stock150ms. Hold timer, surface
handoff, eligibility, compositor ownership and ignore-input scope are unchanged.
The longer reveal can apply to native animated cancellation while an unobscured
blur surface remains; native cleanup still controls its lifecycle. Input stays
suppressed for the native layer lifetime, potentially25/50ms longer, not bypassed.

New string choice wins. Otherwise current boolean true→Low,false→Off. With no
boolean, old off/default→Off, any enabled old setting→Low. No obsolete strength
is silently resurrected. Settings and welcome share identical read logic; both
commit the new choice plus compatible enabled boolean. Darken is disabled while
Off, but its saved preference is preserved for next enable.

The welcome selector remains exactly centered with equal chevron/balance widths.
Width increases92→112dp for Medium; height40dp, end-chevron slot and click behavior
are unchanged. End ellipsis protects very large fonts/localized labels; full text
remains accessible. Existing centered label patch is retained.

This final planner is within the outer transaction journal, AFTER native_blur.
It does not edit white-flash adapters. Integrator must compose any independent
white-flash source postimage before final validation; no build/push was performed.
Host tests use Java/C++ API doubles for policy, exact156 source transformations,
and journal replay/rollback. They do not certify Android compilation or pixels.
