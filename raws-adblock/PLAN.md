# RawS: Brave-native ad blocking, without uBlock Origin

**Decision:** One Sandium blocking service, one global policy (Brave Android Standard). No extension, extension runtime, user-created site exceptions, per-site preferences, Shields panel, or Brave product stack. Domain-scoped filter-list exceptions and first-/third-party classification are still essential: omitting them would change what gets blocked. Default and additional lists are two evaluations inside the same Brave implementation, not two different blockers. This decision supersedes the uBO runtime goal for this experimental path only.

**Status:** LOCAL SOURCE PORT, NOT ENABLED. No APK, GN link, Rust execution, restore, or device-parity result is claimed. The entire change is additive under `raws-adblock/`. It does not modify the RawS feature manifest, pipeline, cache keys or existing Sandium branch. See `pins.json` and `NOTICE.md`.

## Local follow-up: network decisions and native diagnostic

The new adapter retains same-party default-list matches when the **initiator** is YouTube (including mobile subdomains). It does not relabel those requests as third-party or add a user setting. Normal first-party tolerance still applies elsewhere. `ResolveDecision` merges original/alias rule flags, gives important matches precedence, retains substitution data, and allows a valid user-facing rewrite only for GET/HEAD/OPTIONS, never for the DNS alias. These functions return a decision; no live URL loader invokes them yet. DNS/proxy guards and navigation/renderer integration remain outside this commit.

The v2 native diagnostic builds *two* actual Rust filter collections and exercises `MatchStandard` and `ResolveDecision` together in nine fixtures. No test doubles are on the GN target. The separate host unit suite uses doubles to check decision semantics and source/evidence gates; do not use it as a substitute for executing the native binary. The v1 smoke instructions below are superseded by this procedure:

1. Use a disposable, independently prepared RawS 158 `src` with the normal DEPS, runhooks, authorized Siso environment and reviewed RawS changes. Keep canonical checkpoints and all existing `out` directories untouched. Have the pinned Brave Git objects available locally. Read the existing compile-1 job log independently before using any expensive CI path.
2. Run `python3 raws-adblock/stage.py /path/to/brave-core /scratch/src /scratch/overlay-v2`. Inspect the receipt, then copy `overlay-v2/brave` and `overlay-v2/components/sandium_adblock` into the matching, previously absent directories of the **disposable** checkout. Do not overwrite a v1 overlay or merge with a full Brave checkout. `gn` and `autoninja` must resolve to the provisioned Chromium/depot_tools tools; Python 3.11+ required.
3. From the RawS repo, run `python3 raws-adblock/native_smoke.py --src /scratch/src --brave-core /path/to/brave-core`. It regenerates the expected source manifest from pinned Git objects, checks the installed overlay and release args, creates a fresh `out/RawSHostSmoke-*`, and uses `--root-target` to expose the test without editing Chromium's root BUILD.gn. It builds only the host smoke group and its dependencies under the Android configuration. A pass requires a native engine dependency in the graph, successful build, actual executable run and all nine labeled results. The generated JSON and graph are **host proof only**; inspect Siso logs separately for real remote execution. A failed run leaves its output available for diagnosis. Do not loop retries or publish it as a checkpoint.
4. After this passes, link the Android ARM64 target in an isolated feature recipe, implement the live enforcement/renderer steps below, and perform the phone comparison. A host result does not prove Android ABI linkage or parity.

## Exact technical baseline

| Role | Reference |
|---|---|
| Local change parent | `sandeepbimt/Sandium-2`, `raw-sandium/native-ui158`, `35bc6dc0a57cca9cc3dd4fd799434130a831e159` |
| Known comparison build | RawS official158 `e7e782067daef429073e54c2bd8fbb91da7c8439`, service #1396. Stored APK proof SHA-256 `7feb138bacb61dd9f77fca29c579330a2209f1ccd754c5e443962e76a76a977b`. Neither that APK nor the separate Brave-based Sandium #1430 is a result of this port. |
| Chromium Android | 158.0.8127.42, `52bdd21723d5db0c9ab11716d38feac74828cf84`; ARM64 `chrome_public_apk` |
| Brave reference | official Android 1.100.58, corresponding brave-core `bd6d26d1bced03c17a98baa86d2cd3425d543d1b` |
| Engine | Use the vendor tree in the pinned Brave commit, not crates.io HEAD. GN selects `adblock` 0.13.3; upstream Cargo VCS id `886d45dcf5283ce8eddc6d961e7dd27966ab23f2`. |

## What this change implements

* `native/request_matcher.cc` and `standard_merge.h`: a port of the pinned Brave request conversion and **Standard** result composition. The request includes the method, resource type, initiating origin, and Chromium's registrable-domain calculation including private registries. Preserves exceptions across the default and additional collections; suppresses the default collection's first-party blocking with the pinned feature default; preserves third-party important decisions, redirect precedence and additional-list rewrites. This returns a structured decision, not a Boolean cancellation. It is not yet connected to network requests.
* `stage.py`: an offline materializer for a **new staging directory**. Reads the exact Brave Git commit, not uncommitted worktree files. Walks generated Rust dependency labels from the Brave CXX bridge, stages their named vendor source directories, the bridge and resolver, and preserves upstream notices. Applies one narrow GN visibility change to the exact Brave file (`8d01c305…`), stages the new native targets, and writes a file-hash receipt. Only this source-preparation algorithm was tested with synthetic Git trees here. This is not proof of a complete linkable GN graph; indirect GN configs or target-specific dependencies may need a reviewed port. Outputs never go directly into a protected checkout.
* `native/engine_smoke.cc`: a **real-FFI** target that constructs a Rust engine, installs an in-memory list, and checks a positive block, exception, wrong resource type and same-party allowance. It is supplied, not executed in this environment. `tests/` also compiles the real adapter against recording test doubles and exercises the native composition rules separately. Those tests are not Rust or device evidence.
* `probe/`: an eight-outcome browser fixture and comparator. It intentionally rejects equal-but-broken browsers. No synthetic host-test outputs are presented as phone measurements.

## Reproduce the host checks and prepare a candidate

From the RawS repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s raws-adblock/tests -v
# Both inputs are already-populated local source repositories; no network access is needed.
# Use a new scratch directory OUTSIDE both checkouts.
python3 raws-adblock/stage.py /work/brave-core /work/raws/src /work/engine-overlay-001
```

Review `source-receipt.json`, upstream licenses, and GN diffs before admitting any output. In a *disposable* copy of the verified Chromium checkout, install the reviewed `brave/` and `components/sandium_adblock/` subtrees under `src/`. Refuse collisions unless already covered by an exact approved preimage. Do not copy the receipt into Chromium. First try `gn gen` and `gn check` for `//components/sandium_adblock:engine_smoke`, then build that target explicitly in a diagnostic graph (an unreferenced target is not automatically in the `chrome_public_apk` graph; add it to an experiment-only root group for the diagnostic). Run the host executable or deploy the matching ARM64 test executable plus its runtime dependencies. Resolve the *first specific error*, not by importing all of `//brave`. No production branch or CI activation is part of these commands.

## Dependency-ordered implementation plan

| Step | Work | Evidence required before moving on |
|---|---|---|
| 1. Establish clean control | Read the `raws-native-compile-1` log from the UI branch before building this feature. Compare with #1396, whose final compile, packaging and probe succeeded. Preserve the old run's logs and receipts. Resolve or isolate that pre-existing failure independently. | A no-blocker control APK with a known commit and hash, signed/ZIP/ABI checks, proof of launch on the test phone. No assumption that a seed success means a working APK. |
| 2. Link the native engine | Validate the exact vendor closure and bridge in the real RawS workspace; preserve Brave's non-iOS features including single-thread, full regex and CSS validation. Initialize the domain resolver once and own both list engines on a dedicated sequence. Add only reviewed hook/target paths to the RawS adapter recipe. | Real Rust smoke target passes and real RawS build links; target graph proves no browser-extension path is needed. |
| 3. Supply the same filter inputs | Inventory the reference phone's active default/additional and locale-specific list versions, resources, trusted scriptlets, permissions and feature flags. Distinguish packaged bootstrap from updated components. Supply a signed, offline bootstrap and versioned manifest; authenticate updates, bound input sizes, validate before atomic promotion, retain a last-known-good set. Do not point Sandium at Brave's production update infrastructure by assumption. | Exact component IDs, versions, SHA-256s and licenses; clean offline first page is protected; invalid/signature-failed/unparseable update leaves the last set active after restart. |
| 4. Enforce the result | Port the necessary code from `browser/net/brave_ad_block_tp_network_delegate_helper.cc` and its pinned caller. Hook browser requests before dispatch, at re-evaluation on redirects, and at response time for CSP. Match Brave's initiator and method handling, CNAME policy, network-service/worker/frame coverage, redirect substitutes and parameter rewrites. Port top-level domain-block behavior as a separate global navigation check where enabled. Do not persist site switches. | Request traces and server-side logs show both blocks and allows, not just a counter. Real cross-origin requests, aliases, nested frames, navigation, workers, WebSocket, cold start and Incognito individually exercised; gaps reported, not silently counted as matching. |
| 5. Render page effects | Port required pieces of `components/cosmetic_filters` and the corresponding renderer/browser interface and hooks. Match document-start timing, trusted execution contexts, selector exceptions, procedural rules, dynamic elements, and blocked-element collapse. Never grant privileged scriptlet permissions to a downloaded untrusted ruleset. | DOM/computed-style and script-execution observations match Brave; no injection into browser-internal pages; navigation, back/forward and isolated private profiles checked. |
| 6. Release qualification | Build optimized ARM64 Release. Verify the actual APK, SHA-256, signing cert, ABI, clean install and launch with an isolated test identity. Compare on a physical phone against the pinned official Brave Android build. | Archive the reference/candidate APK hashes, device/build, effective configuration, components and seeds, case matrix and sanitized traces. Release only on passing results; no claim of universal parity. |

**Patch scope:** port Brave changes that implement ad/tracker blocking, including their required Chromium hooks. Keep an explicit per-patch ledger: source path, revision/blob, target pre/postimages, purpose, dependencies, regression test, and applied/deferred/excluded decision. Do not apply `brave-core/patches/*`, Bare's separate patch series, P3A, Rewards, Wallet, password or unrelated privacy/UI changes. Do not include a uBO extension or build a uBO runtime. Filter syntax and individual resources have their own provenance; review licenses before redistributing. Report any omitted effective reference inputs as a parity gap.

## Android comparison protocol

**Controlled functional suite.** On an isolated lab network resolve `raws-news.test` and `raws-ads.test` to the fixture server. They must be separate registrable sites; using only different ports on localhost is insufficient. Bind `serve.py` to its lab address (`127.0.0.1` by default):

```sh
python3 raws-adblock/probe/serve.py --bind 192.168.1.20 --port 8080  # substitute the lab host
```

Open `http://raws-news.test:8080/` on the test phone. Record the displayed JSON from (1) a clean no-blocker control, (2) Brave Standard with `probe/rules.txt` active as additional test rules, (3) Sandium with the same additional test inputs. Use a test-only bootstrap for RawS, not a new user setting. Confirm the reference actually loads the fixture rules/resources. Collect net logs and/or server-side request traces independently, and use screenshots for cosmetic outcomes. Script `error` alone can also indicate DNS/CSP/transport failure. The fixture does not itself prove why a network request failed. Logs from the fixture handler are disabled by default; use a lab recording proxy/server for the trace. Run:

```sh
python3 raws-adblock/probe/compare.py control.json brave.json sandium.json
```

Eight cases: benign third-party script runs, target script blocked, explicit exception works, same-party control runs, redirect supplies a substitute, cosmetic element hidden, cosmetic exception visible, and scriptlet has the expected effect. Two browsers that both allow everything fail the gate. If Brave itself does not satisfy a synthetic case, triage the fixture or observed reference behavior first; do not tune Sandium to an invented result.

**Production-equivalence suite (no custom test rules).** Freeze locale, engine/list/resource versions, device, DNS and global mode. Test 30 or more representative pages spanning news, search/social, streaming, shopping, login/consent and payments, using test accounts and no live purchase. Pair cold/warm visits and repeat dynamic cases at least three times; use the same recorded content where possible. Include both expected allows and expected blocks, actual visible ads/placeholders, anti-adblock prompts, video playback, functional navigation/checkout. Add deterministic fixtures for CSP, CNAME, procedural hiding, dynamic iframes, workers, first navigation after cold restart, and list-update rollback. A higher block count cannot compensate for a broken transaction. Record matched/missed/overblocked/inconclusive per case, plus median and p95 page load (LCP where available), transferred bytes, and memory. Gate: no unexplained controlled mismatch, no new critical site breakage, no repeatable missed ad that the reference removes on the agreed suite. Report coverage, including any nondeterministic cases, rather than claiming identical behavior across all sites.

## Build and checkpoint safeguards

No CI trigger is needed for the source-only commit. For the later native integration use Full Mode, at most five cumulative stages; require `use_siso=true`, `use_remoteexec=true`, `use_reclient=false`, and verify actual remote execution, not merely flags. Keep `3c8004b`/job `949` (26 GB) immutable. Verify manifests, shards, workspace and fingerprints; never mix incompatible Brave build objects into the isolated RawS 158 namespace. Use the compatible RawS seed under its admission rules, not an assumed interchangeable cache. Record actual reused objects/actions, remaining work, timings, archive checks and APK status. Never overwrite the last valid checkpoint on compilation or archive failure. Keep existing trigger filters untouched. Do not launch a feature build until the baseline and the local source recipe pass their checks.

### Source map

* RawS pinned branch: `https://github.com/sandeepbimt/Sandium-2/tree/35bc6dc0a57cca9cc3dd4fd799434130a831e159` (lock, feature manifest, CI config, #1396 evidence and architecture).
* Brave source: `https://github.com/brave/brave-core/tree/bd6d26d1bced03c17a98baa86d2cd3425d543d1b` (core/common/adblock/rs + resolver; content/browser/ad_block_engine and ad_block_engine_wrapper; features.cc; third_party/rust/adblock/v0_13/BUILD.gn and the vendored crate's .cargo_vcs_info.json).
* Reference download: `https://github.com/brave/brave-browser/releases/tag/v1.100.58`. Record the actual Android APK's identity and checksums before the comparison.
