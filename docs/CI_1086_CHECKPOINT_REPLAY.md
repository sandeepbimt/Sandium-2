# CircleCI #1086: replay-safe UI identity

## Evidence

Commit `fbaabf3984ae4824208c7b6fd4f050dd1bd3df63`, pipeline1086,
workflow `566144e1-6f88-4e30-bc6b-02af431fd081`, job3241
(`82c96832-f435-457e-894a-1c996f18a4aa`) failed at step141,
“Apply and verify Sandium UI pruning and preference defaults”.
The run stopped before APK compilation, not from the one-hour job limit.

The traceback points to `patch_make_brave_default_label`:

```
RuntimeError: make-brave-default-label-in-chromium-grd: message ID exists but its source text is not the expected Make Chrome default
```

Step135's “update branding” explicitly copied
`brave/browser/ui/android/strings/android_chrome_strings.grd` to
`chrome/browser/ui/android/strings/android_chrome_strings.grd`.
The final branding overlay transforms the canonical Brave copy to Sandium,
while the earlier prune patch accepted only Chrome or Brave. Thus a restored
final-branded tree follows a different path than a pristine source test.
The failed log did not print the actual message body; the Sandium-state cause
is reproduced through the exact copy/rebrand composition, not a direct dump
of the failed worker's file.

## Repair

- Match exactly one `IDS_MAKE_CHROME_DEFAULT`; accept only the complete known
  Chrome, Brave, or Sandium message bodies. Normalize to Sandium immediately.
- Do not accept substrings, extra lines, markup, duplicate IDs or unknown copy.
  On failure report the encountered UI body rather than an unhelpful anchor error.
- Keep removal of old duplicate XML/GN resources intact.
- Change the five stale Brave-only UI acceptance checks to exact message-ID
  checks, accepting upstream Brave or final Sandium only at the early gate.
- Final identity gate requires Sandium, including the actual Chromium default
  browser resource. Legal/service and security-warning checks remain intact.

## Validation

Seven new regression tests cover known states, repeated copy/rebrand order,
unknown/extra-line/markup bodies, duplicate/missing IDs, final identity,
wrong-ID content, and legacy duplicate-resource cleanup. They run in the
existing GitHub self-test workflow. Existing branding checkpoint tests (7)
and visible-branding tests (5) also pass.

The complete pinned Brave `android_brave_strings.grd` and
`android_chrome_strings.grd` files from
`44a84b1f89d9a35287289d6a3d493e362f5a5123` were additionally passed through
three canonical-copy → prune → early validation → final branding → final
validation cycles. All passed. This is a real-source string-overlay replay,
not a full downloaded CircleCI workspace replay or native Android build.
The next CircleCI run must pass step141 and then compile/package the APK;
a local gate pass does not prove Java compilation or device behavior.

## Future update rule

When an overlay modifies files that a later preparation step copies elsewhere,
test both the pristine and restored-final inputs using the actual copy order.
Do not weaken expected product semantics or erase full cached source trees
just to make an anchor pass. Retain strict stable-ID and exact-copy validation.
