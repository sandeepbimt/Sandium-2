# Neutral Brave / RawS fixture bank

The older v1/v2 outcomes and qualified passive comparator are unchanged. This
bank tests controlled behavior, not the efficacy of specific public lists or
real sites. No deploy, external requests, real account data, web navigation
changes, element overrides or shipped-list changes are needed.

## Repeatable setup

1. Use fresh **isolated lab profiles**, app identity and APK digest logged
   separately. Set up local split DNS for `raws-news.test` and `raws-ads.test`
   pointing to the same fixture server. These are distinct registrable sites.
   Keep ordinary profiles, credentials and browsing off this lab network.
2. Run `python3 serve.py --bind <lab-address> --port 8080 --log <new-file.jsonl>`.
   Each passive run opens
   `http://raws-news.test:8080/fixture?run=<unique-24-lowercase-hex>`.
   For each browser collect Shields **off** first, then the exact supported
   synthetic passive rule bytes in the same **additional URL** test-only
   provider and effective Standard policy, Shields **on**. Verify actual
   parser/admission and native request evidence; note unsupported rules.
   Keep the same 30 base list revisions/byte digests across profiles; the
   synthetic lane is a separate test-only input, not a new production list.
   If this cannot be configured equally, label the result unqualified.
3. Save the on-page JSON and server event bytes for each run as
   `brave-off.json/.jsonl`, `brave-on.json/.jsonl`, `raws-off.json/.jsonl`,
   `raws-on.json/.jsonl`. Entire logs may be copied for each capture;
   the comparator matches unique run IDs. The server records only synthetic
   route, token and planned status. The first hop must be observed as 302,
   the blocked destination must be absent only with Shields on, and allowed,
   exception and unrelated images must load with matching server evidence.
   A native block receipt is still needed to exclude unrelated causes.
   Never equate this with resource replacement or JavaScript navigation.
4. Repeat the whole four-run set after a warm reload using fresh run IDs.
   `python3 compare.py passive <capture-dir>` returns expected/observed per
   case and invalid controls, not a percentage. Standard DOM hiding/exception,
   late generic insertion, clean editorial visibility and simple form/click
   event preservation are independent rows. The interaction check is
   synthetic (not a payment, sign-in, or website access test).

## Separate reviewed-scriptlet lane

Use a lab certificate trusted for **both** names, HTTPS/443, no TLS-validation
bypass. Bind a suitable already authorized lab listener or TLS front end;
`serve.py` accepts `--cert` and `--key`. Use
`https://raws-news.test/fixture-scriptlet/<unique-24-lowercase-hex>` with
**no query or fragment**. A positive operation removes only the fixed
`data-ppcnt_ads` on an HTML `main[onclick]`; the exact uninject control keeps
`data-popunder-url`. Existing event handler attributes and ordinary form
controls must remain. There are intentionally no dynamic/privileged
scriptlet, arbitrary JS, or main-world effects in this bank.

The exact RawS draft is default **off**, and its native reviewed shadow
projection checks existing slot0. A stock APK or an additional URL input is
**not** proof of positive eligibility. Leave the positive test **not run** until
an isolated instrumented lab build can prove exact same provider preimages,
source permissions and explicit activation on both sides, without modifying
normal profiles, loosening any origin restrictions, or granting trust to
downloaded script. A same-name operation in Brave with unmatched source trust
remains unqualified. No scriptlet network requests are expected; provide
empty server logs for this lane if no image route was hit.

## Evidence sidecar

Use `--evidence <file.json> --brave-source <exact-sha> --raws-source <exact-sha>`
only after verifying actual original logs,
admission and identities. The schema is `raws-neutral-evidence/1`. Include
`inventory` (exactly 30 list identifiers → effective byte SHA-256) and
`runs` with the four labels above. For each label record `platform` =
`android-arm64`, observed `apk` SHA-256, `package`, exact commit `source`,
`phase` (cold/warm), effective `policy`, `provider`, `trust`, `activation`,
and digests `contents` (exact lane rules), `inventory` (canonical sorted
compact JSON), `report` (raw JSON bytes), `parser` (original admission
receipt), `native` (original device evidence), `transport` (raw log bytes).
For off captures use policy=off, provider/trust=none, activation=off, and
null contents/parser; the other evidence is still required. Passive on
records use standard/additional-url/zero-privilege/none; reviewed on uses
standard/instrumented-slot0/zero-privilege-reviewed/explicit-lab-only.
A sidecar binds files but is a declaration, not proof of receipt authenticity
or authority to run. No parity claim from matching fixture outputs alone.

Unit-check server 302 and comparator guardrails with `python3 -m unittest
test_bank` from this directory. Host models do not count as browser runs.
