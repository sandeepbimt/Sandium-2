# External-service-only Android Autofill

Request: remove the built-in “Autofill with Sandium” choice after disabling that
engine; expose “Autofill using another service” as a native switch, default OFF.

## UI and migration contract

The existing localized external-service title is reused by ChromeSwitchPreference.
The two-radio layout is no longer inflated. The fragment and binder use a boolean
switch; the existing mediator remains authoritative. Preference-local persistence
is disabled, so it cannot create a second source of truth. The listener returns
false after passing the request to the mediator: model updates set the displayed
state, including synchronous cancellation when a dialog is unavailable.

No profile migration, preference clearing, or stored-data deletion is performed.
Pinned Chromium already registers `kAutofillUsingPlatformAutofill` false. Existing
explicit true remains true; forcing false every launch would break the user's
existing provider opt-in. Native provider availability, policy, Android service
picker, stored-provider restoration, confirmation and restart remain unchanged.
Cancelled restart restores the actual saved preference. An unavailable provider
may follow Chromium's own existing preference handling, but cannot silently
activate Sandium's internal fill engine because the runtime gates remain OFF.

## Runtime ownership

Keep native Autofill/client/data objects, profile stores, password settings and
security consumers intact. Disable Android built-in user-facing filling/save
entry points; do not remove clients or reuse AndroidAutofillClient as an inert
fallback. The actual platform path has its own AndroidAutofillClient/manager;
TabHelpers only creates ChromePasswordManagerClient for the non-platform path.
Non-Android methods retain original behavior.

The change does not delete saved passwords, cards or addresses. It does not
remove core WebAuthn/passkey authentication, password settings, or wipe normal
application data. However, hiding the built-in keyboard Autofill accessory also
removes passkey access through that accessory; its separate WebAuthn flow is not
changed. Do not describe all passkey UI as unaffected. It is not a proposal to block authentication unrelated to
browser form Autofill.

## Integration and validation

Apply `apply.py SRC` after normal UI composition; `--verify-only` checks replay.
All source anchors across UI and runtime validate before any write. Exact source
reset paths are listed in integration-plan.json only; the historical canonical removal receipt inventory is unchanged.
Stage29 and disposable full composition invoke the same driver. `apply.py SRC --off` restores verified journal preimages (refusing unrelated
source modifications). Disable stage29 wiring before rollback; data
needs no restoration because it was never rewritten.

Focused host tests compile actual extracted Java confirmation methods/listener
and C++ gate code with explicit doubles. Full pinned fixture transforms are
hash-checked and replay checked; drift/partial overlays fail closed. These tests
are not an Android build, generated JNI check, device UI test, or proof of every
possible future/manual credential path. Device acceptance still needs fresh and
existing-opt-in profiles, switch cancellation/restart, missing provider, policy,
private tabs and saved-data persistence. No push or CI run is part of this patch.
