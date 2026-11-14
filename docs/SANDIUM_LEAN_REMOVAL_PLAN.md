# Sandium lean Android: removal plan and retained learning

Recorded: 2026-11-13. Scope: `sandeepbimt/Sandium-2`, Brave-based Android only.
Status: documented plan, not implemented or release-qualified. Do not mix this
work with Bare, Iceraven, Aerium or Afterbird histories.

## Owner decisions and meaning

Sandeep requested analysis of Brave Origin, then a careful plan to remove all
13 component groups, not simply turn them off, and explicitly asked that the
learning be documented for future updates (2026-11-13, 12:10–12:12 UTC).
Use one Flow pipeline, not separate Fast/Full modes. Future Sandium features
should be selectable patches/product recipes, but that catalogue is not yet
implemented. Planning/documentation does not itself authorize new CI runs.

“Removed” means the feature implementation is excluded from the shipping
build and APK, with its exclusive UI, startup services and background work
removed. Its original source can remain in the pinned source checkout for
reproducibility. Shared code needed by retained functions, legal notices and
harmless migration identifiers may remain. A hidden preference, false runtime
flag, absent button or plain string search is not proof of removal.

## Known-good reference and evidence boundary

- Sandium commit: `952b614ef375ec524954c27997d0e491936d21cb`.
- Branch: `experiment/flow-crash-20261113`.
- CircleCI run: **#1075**, workflow `9ba34414-14e7-40b5-83b1-f121c2de53a2`.
- Brave: `v1.98.62`, `44a84b1f89d9a35287289d6a3d493e362f5a5123`.
- Chromium: `d331de35ca8ab1358c7a17e4bd41627d55eaef51`.
- ARM64 release; Siso + BuildBuddy, one-hour CircleCI job ceiling.
- #1075 succeeded in 33m06s; APK build 8m50s, delta capture 7m23s,
  payload save 41s. Experimental head was published; no canonical promotion.
- The owner reported “this time no crash, all looks good thanks” at 11:58 UTC.
  This is device acceptance of exercised behavior, not an exhaustive test suite.
- Preserve this reference and its checkpoint as rollback, not as evidence that
  stripping has already happened.

Current source materialization contains transformation scripts and pin IDs,
not the full upstream source tree. Exact GN dependency closures, all Android
call sites and migrations must be audited against that complete pinned tree.

## Origin product distinction

Official Origin's Android upgrade disables features via policies. The separate
standalone desktop edition compiles extras out. Sandium's requested Android
product therefore goes beyond merely copying Android Origin behavior.
Current upstream Origin branding flags reject Android; do not assume setting
`is_brave_origin_branded=true` works on this pin. Do not bypass paid entitlement
or service authentication. Build independently branded Sandium from source.

## Scope ledger: all 13 groups

The earlier 15-line chat list split reporting into three. The scope is unchanged:
12 feature groups plus one reporting group containing all three reporting items.

| Group | Baseline treatment/knowledge | Planned outcome |
|---|---|---|
| Email aliases | Upstream Android default reportedly excludes; confirm exact pin | Evidence of absence, or remove exclusive integrations |
| Leo/AI Chat | Native/Android implementation preserved, UI hidden | Remove implementation, services, bridges, UI and calls |
| News | Native implementation preserved, UI hidden | Remove feed/NTP integration and fetching |
| Playlist | Runtime allowed check/factory suppressed; Android assumes enabled | Proper build exclusion with Android dependency adaptation |
| Rewards + Brave Ads | Implementation retained; UI/promotions hidden | Remove Rewards and browser advertising, not Shields |
| Speedreader | GN exclusion requested; artifact not audited | Verify engine/hooks/resources absent |
| Talk | GN exclusion requested; artifact not audited | Remove browser integration, preserve website WebRTC |
| Tor | GN exclusion requested; Android applicability needs proof | Exclude Tor integration, preserve normal private tabs |
| VPN | Native implementation preserved, UI hidden | Remove all implementations present in pin and exclusive Android services |
| Wallet + Web3 domains | Implementation retained; UI hidden/defaults off | Remove wallet/provider injection/domain integration |
| Wayback Machine | GN exclusion requested; artifact not audited | Remove browser helper; normal archive.org access remains |
| Web Discovery Project | GN exclusion requested; relevant reference guarded | Remove collection/upload/startup integration |
| Reporting: daily ping, crash reporting, P3A | Preferences/defaults off, not full removal | Remove remote reporting producers/schedulers/upload paths |

Do not infer Android applicability from a cross-platform marketing list.

## Preserve explicitly

Shields, ad/tracker blocking, filter updates, HTTPS protections, fingerprinting
protections, security updates and required component updates; core navigation,
tabs/private tabs, storage, bookmarks, passwords/autofill, permissions, downloads,
media, WebRTC, WebCrypto and ordinary DNS/HTTPS. Keep Sandium welcome/branding,
Balanced S boundary animation, crash fixes and existing intended feature work.
Sync or other useful browsing features are not automatically in removal scope.
Keep local Android/logcat diagnostics; remote reporting removal is not deletion
of every crash-handling facility.

Never silently destroy existing wallet or other valuable user data. Inert legacy
data may remain without active feature code. Export/deletion policy needs its
own explicit decision. Old prefs or background jobs must not reactivate modules.

## Why the existing scripts must change carefully

The green baseline intentionally preserves native modules because previous
large disable bundles broke Android linkage. Relevant repository paths:

- `.circleci/scripts/prepare-brave-source.sh`: current GN recipe and exclusions.
- `.circleci/scripts/apply-sandium-ui-prune.py`: visibility changes, not removal.
- `.circleci/scripts/verify-sandium-vanilla-brave.py`: restores AI/Wallet/News,
  clears overrides and verifies retained implementations/Android linkage.
- `.circleci/scripts/test-sandium-ui-prune.py` and
  `test-sandium-feature-policies.py`: currently forbid key GN disable flags.
- `.circleci/scripts/apply-sandium-full-overlays.py`: mixed overlays, Playlist
  runtime block and prior Android dependency assumptions.

Replace this old verification contract with recipe-derived absence and
preservation tests; do not simply delete failing tests. Restore pinned upstream
once BEFORE overlays. Late `git restore` previously erased adblock registration
and caused a startup crash. Deterministic, idempotent patch order is essential.
Other recent lessons: typography used an inappropriate JavaScript execution
path and caused native abort; removed settings XML required a Java presence
guard; checkpoint capture refused open writers until the known Python build
server was cleanly stopped. Avoid broad suppression of checks or unknown writers.

## Implementation stages and gates

0. **Recipe safety and inventory.** Define a lean product manifest within Flow;
   inventory targets, Java, JNI/Mojo, resources, services, prefs, endpoints and
   data. Separate removal patches from mixed UI overlays. Reproduce the good
   recipe under the new manifest before removal. Preserve signing/package
   identity and a valid upgrade version; never place secrets in manifests.
1. **Lower-coupling integrations:** email aliases, Talk, Wayback, Speedreader,
   Tor and Web Discovery. Prove non-applicability where appropriate.
2. **News and VPN:** remove exclusive code/resources/services; separate builds
   if their dependency graphs are independent.
3. **Leo:** repair unconditional Android dependencies in `browser/android/BUILD.gn`
   and `browser/android/brave_tab_features.cc/.h`, plus generated bridges.
4. **Rewards + Brave Ads:** distinguish all advertising-service code from
   retained Shields/adblock. Never remove every path containing “ads”.
5. **Wallet + Web3:** remove renderer providers/bridges while preserving shared
   crypto, TLS, WebCrypto and authentication functionality.
6. **Playlist:** resolve the pinned Android enabled assumption rather than
   merely deleting an assertion. Preserve ordinary media behavior.
7. **Reporting:** remove all three remote reporting mechanisms and safely unwind
   their consumers; retain necessary local diagnostics and security updates.

Order is provisional until the pinned dependency audit. Build and test each
independent batch before continuing. A successful compile alone is not completion.

## Proof and upgrade test contract

For EACH group maintain a ledger with pin, targets, call sites, Java/JNI/Mojo,
manifest/resources, services/jobs, endpoints, data handling, retained shared
code, and evidence/status: absent upstream / removed and verified / blocked /
untested. Record every failure, its cause, corrective patch and regression test.

Required evidence:

1. `gn desc`/`gn refs` dependency closure and link inputs exclude implementation.
2. APK DEX, resources, assets and manifest exclude feature-exclusive content.
   Link-map/object evidence supplements symbols; stripped symbols alone prove
   nothing. Check stale generated files and deleted build inputs.
3. No startup factory, observer, provider, deep link, scheduler or policy can
   instantiate/re-enable the feature.
4. Controlled runtime/network checks show no feature-specific requests; static
   endpoint/client review complements finite captures. Website traffic is not
   automatically browser service traffic.
5. Fresh install AND upgrade from #1075, including legacy feature-enabled prefs,
   startup, first-run, restart, force-stop, background/foreground, offline/online,
   settings/search, navigation, private tabs, media, downloads, permissions,
   passwords/bookmarks, Shields and filter update regression checks.
6. Match APK to exact source/recipe and retain the required source/licence notices.

Final gate: a clean-output build without old prepared-output dependence and an
incremental build of the SAME recipe agree on package/function evidence. Measure
APK size, startup, build and checkpoint timing; promise no exact savings before
measurement. Canonical promotion requires acceptance, not merely green CI.

## Flow safety and outstanding proof

- One Flow pipeline; a product recipe is NOT a Fast/Full execution mode.
- Bind heads, manifests, APK completion receipts to a digest of upstream pins,
  toolchain/ABI/build type, effective GN args, feature selection, patch contents
  and order, preparation scripts, and checkpoint schema.
- Current compatibility string is fixed, not a complete product fingerprint:
  `brave-44a84b1-chromium-d331de3-arm64-release-single-v1`.
- Old APK completion cannot satisfy the lean recipe. Use isolated checkpoint
  lineage; reuse unchanged compilation actions only when dependency validation
  allows it. Do not overwrite the known-good canonical base.
- #1075 saved a delta successfully. Stages 2–5 accepted its completion marker in
  seconds, so they did NOT reconstruct base plus delta. Real save → subsequent
  full reconstruction → resumed build still needs demonstration without the
  completion shortcut. Check all chain ordering, hashes and deletion tombstones.
- Publish head only after payload upload/integrity checks; failure leaves prior
  valid head intact. Distinguish resumable stage success from a verified APK.
- Budget restore/preparation/GN/build/shutdown/capture/upload below one hour per
  job, with reserve time and clean compilation stop for checkpointing.
- Existing base restore uses up to 8 workers; historical base codec uses
  zstd `--fast=5`. New delta parallel compression prototype is separate and
  unintegrated. Do not claim all deltas already use 8 workers/fast5 or combine
  codec rollout with feature stripping.

## Licence and ownership learning

Source-built reuse under applicable licences is distinct from rebranding an
official binary or using Brave-hosted services. MPL-covered modifications need
matching source availability to recipients and preserved notices. Chromium and
bundled dependencies/filter lists have separate requirements. Keep a shipped
component licence inventory. Private source access alone does not satisfy
external recipients' source access needs.

Sandium owns its original contributions/brand, not retained Brave/Chromium code
merely renamed. MPL is file-level and does not grant trademarks. Original
independent replacements can reduce dependency over time, but superficial or
AI-generated rewrites of upstream code are not clean-room proof. uBO syntax
support, filter-list distribution and copying GPLv3 uBO code are separate
licensing choices. Do not assume all lists/scriptlets share one licence. Review
service endpoints/credentials separately; obtain legal review for public or
commercial release. This is a compliance plan, not legal clearance.

## Future update checklist

Before any Brave/Chromium pin update: read this document, diff upstream feature
and build changes, re-audit Android assumptions and endpoints, rebase each
removal patch independently, update recipe identity, validate clean and
incremental builds, repeat absence/upgrade/security tests and update the ledger.
Do not revive old preserved-module tests or late restore ordering. Do not carry
forward “removed” status without evidence for the new pin. Record date, revision,
change, reason, test evidence, unresolved risks and rollback reference here or
in linked per-component records.

## Primary sources reviewed 2026-11-13

- https://support.brave.app/hc/en-us/articles/38561489788173-What-is-Brave-Origin
- https://brave.com/origin/
- https://raw.githubusercontent.com/brave/brave-core/master/components/brave_origin/buildflags/buildflags.gni
  (master evidence, not proof of exact pin behavior)
- https://github.com/brave/brave-core/blob/master/LICENSE
- https://www.mozilla.org/en-US/MPL/2.0/
- https://www.mozilla.org/en-US/MPL/2.0/FAQ/
- https://brave.com/terms-of-use/
- https://chromium.googlesource.com/chromium/src/+/main/LICENSE
- https://chromium.googlesource.com/chromium/src/+/main/docs/adding_to_third_party.md
- https://www.chromium.org/developers/how-tos/api-keys/
- https://github.com/brave/adblock-rust
- https://github.com/gorhill/uBlock/blob/master/LICENSE.txt
- https://easylist.to/pages/licence.html

Repository evidence is pinned to commit `952b614ef375ec524954c27997d0e491936d21cb`.
Do not confuse current upstream master documentation with a pin-specific audit.

