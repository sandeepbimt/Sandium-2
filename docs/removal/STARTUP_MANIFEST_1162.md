# #1162 launch failure: retained Android manifest components

## Evidence

The user's 2026-11-15 07:30 IST bugreport shows installation followed by a launch
at 07:30:27. The main activity requests an internal activity (`j7j` after R8),
Android returns activity-not-found (`-92`), and the main activity finishes.
There is no new fatal Java/native exception for this launch. Historical crash
buffer entries from earlier APKs must not be mistaken for this failure.

Independent inspection of the exact #1162 APK found no manifest declaration for
`WelcomeOnboardingActivity`, although the first-run code still launches it.
The obfuscated class name alone is not a deobfuscation proof.

## Root cause and fix

The Playlist removal recipe had an exact replacement generated from an overbroad
XML match. It removed a contiguous block starting at BraveAccountCustomTabActivity
and ending at BraveSettingsActivity, including WelcomeOnboardingActivity.
Narrow the replacement to PlaylistHostActivity alone.

VPN, Wallet and Leo manifest regexes had the same adjacent-component hazard:
greedy opening-tag matching could consume the slash of a self-closing tag and
then continue through a subsequent paired activity. Use non-greedy opening tags
and disallow the paired-tag alternative on a self-closing opening tag.

No feature engine or payment gate is restored. The corrected pinned composition
removes exactly 23 intended feature components and preserves all 14 unrelated
components, including their attributes and child elements. The mandatory pinned
manifest reset repairs manifests from previously damaged checkpoints.

## Regression gates and verification limits

- Test the complete pinned manifest against a retained-component inventory, not
  just absence of removed names.
- Test self-closing and paired removed and neighboring tags independently.
- Assert onboarding/settings/custom-tab activity names during full source replay
  and in the real APK's manifest string pool. The recipe-bound APK gate requires
  a manifest; these positive checks supplement existing package validation.
- The updated APK gate rejects the exact #1162 APK for missing onboarding.
- Run the full suite and pinned UI/removal composition, reset/replay and
  interruption-recovery checks before publication.

These static checks do not replace an Android cold-launch test, first-run
completion, upgrade tests, or device validation. A green compiler never proves
that Android can resolve every runtime activity or that the application works.
