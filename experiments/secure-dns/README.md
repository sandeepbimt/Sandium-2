# Browser-global Secure DNS controls (pinned Chromium 156)

Uses the existing SecureDnsBridge, Local State preferences and Chromium resolver.
No second DNS implementation, system Private DNS changes, new dependency, restart,
or background benchmark is introduced. Native Android default-Off is owned by
`default_mode.py`; existing explicit user and managed values retain precedence.
No facade getter writes settings.

The provider picker has Off, Cloudflare (1.1.1.1), Google Public DNS, Quad9,
saved custom providers, and an existing Automatic/unknown custom choice when
needed to represent current native state truthfully. Selecting a named provider
first validates/sets its config, then selects native SECURE mode. Off preserves
its endpoint for later deliberate reuse. No switch silently selects Cloudflare.
Welcome and Shields use the same facade and browser-global state.

Settings permits adding named HTTPS DoH templates, an OPTIONAL explicit Test,
and removing saved entries. Save validates native syntax without changing the
active resolver. Test invokes the existing blocking native probe on an auxiliary
thread only; no implicit tests on opening, typing, saving, or loading pages.
Dialog lifecycle tokens prevent stale callbacks after dismissal. Removing an
active saved entry preserves native DNS and displays Current custom provider.
Tests use a probe request, not browsing history. Current providers may see DNS
queries after the user selects them. Custom URLs reject credentials/fragments.

Policies for both mode AND templates, plus native management restrictions, are
respected. Parent/enterprise restrictions remain upstream. Managed policies can
still override the native Off default. The provider speed varies by network;
this does not fix rendering or guarantee faster pages. Quad9's security filter
is not equivalent to the browser's content adblocker.

Source registration: existing //chrome/browser/privacy:java and :java_resources.
Its resource package is org.chromium.chrome.browser.privacy.secure_dns.
Pinned chrome/android:chrome_java already depends on that target (line492 of
upstream d331de35); Brave welcome/shields compile via brave_java_sources.gni,
not a nonexistent //brave/android:java target. Existing SecureDnsSettings is
replaced at its normal navigation destination; its public summary/title/search
entry remain available. Existing R.string.text_off is used by original Settings.

The source journal restores before source preparation. Historical removal
inventory is unchanged. Apply validates all inputs before writes, supports
verify/replay/off, and refuses unknown source conflicts. Tests cover pinned
input hashes, composition/rollback/conflicts, emitted Java facade execution
against platform/native stubs, policies, no implicit mutation/probe, existing
Automatic, custom save/select/remove, URL validation, and callback source gates.
No full Android compilation or runtime DNS/device verification is claimed.

Provider endpoints: https://developers.cloudflare.com/1.1.1.1/infrastructure/network-operators/
https://developers.google.com/speed/public-dns/docs/secure-transports
https://docs.quad9.net/services/
