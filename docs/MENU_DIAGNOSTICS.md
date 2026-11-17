# Menu persistence evidence, #1315 follow-up

No new Android disk-loss root cause was reproduced. Keep canonical storage and behavior.
Previous fixes already present: per-completed-edit commit; unified app-context namespace;
native Settings sharing canonical layout. Do not describe this instrumentation as a fix.

Optional numeric receiver is registered per ModelList by the actual profile-owning
producer. Missing/unknown/private profile must not register. The appmenu module does
not guess a profile and does not depend on the recorder. Integrator must wire the
BraveTabbedAppMenuPropertiesDelegate callback to the recorder with actual profile
checks; without that bridge these hooks intentionally record nothing.

Event contract (append-only recorder IDs):
- 16 MENU_READ(5): local edit sequence (0 on open), source (1 presenter), validity
  (0 absent, 1 valid, -1 invalid), stored key count, canonical membership/order fingerprint.
- 17 MENU_SAVE(6): incremented sequence, source1, validity1, key count, attempted
  canonical fingerprint, commit outcome (1 successful, 0 failed).
- 18 MENU_RENDER(5): local edit sequence, screen (0 quick, 1 All Menu, 2 editor),
  projected action count, order fingerprint, requested page. Emitted at render start,
  not proof that a frame was presented; page may subsequently clamp to available range.

Fingerprints are bounded unsigned32bit values over frozen numeric product action IDs
(and hidden bits for canonical state), not Java string hashes. Unknown/custom keys are
excluded. No names, URLs, titles, configuration strings or raw serialized state leave
the menu. Counts include unknown entries but cannot identify them. Some toolbar actions
may remain unmapped: fingerprint coverage is explicitly partial. Fixed Library strip
is excluded from render fingerprints. All Menu intentionally shows hidden shortcuts.

These events show whether completed writes and next-open reads agree, and distinguish
storage from projection. They do not prove disk durability across Android process death.
A malformed load still uses existing default fallback; this change does not alter it.

Validation: actual extracted presenter writeLayout/persistDraft/finishEditing methods
compiled and exercised with real file save/reopen, completed edit without Done, Done,
and explicit Cancel; actual State/Metadata Java compiled too. Receiver absence/removal
and unknown-key exclusion tested. Existing preference/restart suites use file-backed
Android stand-ins. No Android view lifecycle/process-death test or device run performed.
