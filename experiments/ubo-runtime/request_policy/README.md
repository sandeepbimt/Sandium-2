# Per-request native Shields policy (inactive experiment)

Apply after loader, Shields bridge and routing, then regenerate GN. Reset this
layer first, before the underlying layers. Ownership receipt rejects foreign
changes rather than clobbering them.

Both pinned Chromium webRequest dispatch modes invoke an embedder virtual hook
**after recipient permission filtering**. The base implementation is a no-op.
Brave supplies fields only for the fixed component ID, expected uBO version,
component manifest location, same regular profile and enabled registry entry.
Other extensions and private/cross-profile delivery receive no fields.

`details.sandiumShields` contains protocol, selected owner generation,
engineOwned, shieldsEnabled, adControl, cosmeticControl and contextSource.
Settings are evaluated synchronously by the original native Shields helpers,
not by copying and reimplementing ContentSettingsPattern rules in JavaScript.
Top navigations use destination origin; frame requests use the real outermost
frame's committed origin; frameless workers use their native initiator. An
unavailable origin uses native default lookup, matching Brave's empty context
fallback rather than deriving a hostname from the resource/advertisement URL.

The generic virtual capability `SupportsPrivateWebRequestPolicy(extension_id)`
defaults false and the Brave override returns true only for this fixed ID. It
can tell native readiness code that this API client implements the policy hook;
it is **not** proof that actual Android filtering or smoke tests have passed.

Renderer `web_request_event.js` at pinned Chromium d331de35 deep-copies details
and removes only the listener's optional keys and security-info fields. The
private nested dictionary survives this path. A test executes the exact pinned
function to check preservation. Legacy dispatch forwards its argument object
without that grouped filtering layer.

Tests cover exact-source overlay application/reset, both dispatch recipients,
identity restrictions and grouped renderer preservation. Native compilation,
startup coordination, network filtering, cosmetics, and real-device Shields
parity remain separate unpassed gates. This layer does not select an engine.

## Policy semantics and counters

Sandium's two-state Shields overlay (`apply-sandium-shields-two-state.py`)
changes the native cosmetic default to BLOCK and migrates legacy standard/default
to BLOCK: public On is aggressive and Off is allow. This adapter preserves that
public control, not exact Brave standard-mode first-party/procedural heuristics
for hidden or externally injected legacy values. Cosmetic policy is independent
of network Ads policy, matching native IsCosmeticFilteringEnabled.

`pageEpoch` is the committed NavigationEntry unique ID for framed subresources;
main navigations and frameless workers use zero and must not contribute counters
to the previous page. This is a stale-counter guard, not a navigation identifier.
