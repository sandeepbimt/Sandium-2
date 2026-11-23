# RawS / Brave comparison: desktop control and Android qualification

Reference source: Brave Core `bd6d26d1bced03c17a98baa86d2cd3425d543d1b`
(Brave Android 1.100.58). Baseline RawS: signed #1517,
`aa8a8f63eb541a2c2dbac9cb810935bceb982e0b`. Compare on a neutral
test profile before checking public pages. Do not use one-off site patches
as evidence of parity.

## Run the matched tests

1. On an isolated test network, resolve `raws-news.test` and
   `raws-ads.test` to the server and run `serve.py --bind <lab-ip>`. Verify
   both origins are reachable first; they must remain distinct registrable
   sites. Do not point real browser profiles or browsing data at the fixture.
2. Load the exact same `rules.txt` into the Brave and RawS test profiles using
   the equivalent engine input lane, and keep it out of the unblocked control.
   Save each runtime's active list revisions and hashes, app/APK identity,
   effective Shields mode and time. A synthetic scriptlet belongs in a test
   lane explicitly authorized to use that reviewed bundled resource, never in
   a production subscription granted extra privileges for the sake of this test.
3. On the same device, run `/cosmetic-parity` first cold, then warm in each
   browser. Save the exact on-page JSON separately. Pass the three captures
   to `python3 compare.py control.json brave.json raws.json`. Repeat with
   ad blocking off to check clean behavior. If a Brave control fails, report
   the failed observation rather than tuning RawS to a guessed reference.
4. Record redirect/network attribution independently. A script that failed
   could indicate transport, DNS or CSP rather than blocking. The small
   comparator validates its listed visible outcomes, not request provenance,
   publisher coverage or browser-wide parity.

This adds exact expectations for late scoped hides, late generic rules,
domain exceptions to generic rules, selective procedural hiding, and normal
content. The original URL (/ and version 1) still works. The comparator
rejects missing cases, mismatched fixture versions and equal-but-broken runs.

## What this does not prove

Measure real rule input coverage independently of the toggle count. Verify
pre/post-redirect requests and resource substitution, document-start and
late mutations, rule-list reload, official source permissions and packaged
resource versions. Keep native Chromium navigation, isolation, consent,
authentication and payment working. Validate these paths on an Android
build before calling them shipped or making a Brave-parity claim.
