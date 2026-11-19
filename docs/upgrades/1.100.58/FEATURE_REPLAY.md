# Exact158 replay record

This record distinguishes local source replay from GN, compilation and device
verification. None of the rows below is evidence of an APK or phone result.

| Feature | Actual upstream change / adaptation | Local proof |
|---|---|---|
| Native UI | ToolbarPhone refactor changed home visibility and tab-switcher coordinator access; menu customization comment now includes site controls | 55 Git-blob/SHA-bound inputs, six relevant Brave patches, ten overlay apply/readback/replay operations; comprehensive tests |
| Navigation capture | Upstream removed shouldCaptureWhileHidden/getTopControlHiddenRatio and now uses actual visibility/dirty state for SPA capture | Preserve new native branch instead of reconstructing obsolete workaround; four ordered plans replayed |
| Native blur | Preserve158 manager, header and default feature parameters; separate dim only; fix Settings marker indentation/key replay | Exact source fixtures, native Off/On preference migration and repeated composition tests |
| Welcome | Existing actual158 activity/source-list/restart/resource anchors remain compatible | Full welcome apply and replay against five authenticated inputs; 14 welcome regressions plus wrong-pin rejection |
| Download bootstrap concurrency | Existing three native Download Service constant anchors remain compatible | Exact158 config replay retains 8 concurrent, 8 running and64 scheduled values; no new transfer engine |
| Adblocking and Shields | Six existing subscription/bootstrap/race/resource/two-state/warmup adapters replay unchanged | 41 authenticated official inputs and per-stage idempotence; native compilation and first-launch tests pending |
| Playlist/Billing/News | News ViewHolder dispatch became switch-based | Exact News adaptation retains top sites, stats and image credit; Playlist/Billing source replays unchanged |
| Reset and ownership | Added compiler and native generator ownership; generated Siso inputs remain generated-overwrite rather than fictitious Git-owned paths | 352 Brave,127 Chromium files and19 Brave patches authenticated and replayed by production reset function |
| Compiler and Siso | Brave generator formatting changed; build entrypoint moved to TypeScript | Whole-file pre/postimage checks; retain pinned remote container/native flags; fresh official GN command constructed, not yet executed |
| Notifications | Preserve standard Android permission delegate, defer pending request to actual homepage presentation | Exact upstream plus Brave patch replay, nullable declaration compilation, final read-only checker; full Android/NullAway and phone tests pending |
| Lint | Upstream158 policy differs; old156 inventory is not portable approval | Exact target policy retained with zero extra exceptions.954 historical declarations present, three absent, seven owned await final composition. Target lint outcome unknown |

## Lessons for the next update

1. Pin the wrapper/core/Chromium tuple and authenticate full input bytes before
   changing a guard. A matching method name or an unchanged filename is not proof.
2. Replay the complete reset and all applicable Brave patches before overlays.
   An individual transform failure on a bare Chromium input may be a missing
   prerequisite, not a new upstream incompatibility.
3. Keep actual source acquisition, product preparation, GN readiness and APK
   acceptance separate. Never accept the old156 output archive as158 completion.
4. Avoid the legacy intermediate verifier's source-restoring side effects:
   the new158 integrity path verifies the retained Morphe postimage instead of
   undoing it. Historical156 behavior remains frozen.
5. Generated source order matters. Immediate idempotence of one overlay does not
   authorize arbitrary replay after later overlays; reset before the whole pass.
6. Preserve new upstream behavior when it supersedes a workaround. The158 capture
   visibility change is an example; do not recreate old code simply to fit an anchor.
7. Compare broad tests against the exact old baseline. Historical config tests
   are not the selected Full-U preflight, and old lint provenance must not be
   weakened merely to make their counts green.
8. Include all tracked feature assets in checkpoint recipe identity, including
   root android resources and Java payloads, not just scripts and experiments.
9. Bound verification subprocesses as well as compilation. A whole-tree or GN
   verifier can consume the archive reserve if it runs outside the deadline.
10. APK exporter exit0 is not success: require all audit status gates, ARM64-only
    native payload, exact exported bytes and a fresh archive readback. Signature
    validity alone does not establish certificate parity with the previous APK.

## Reuse without unsupported speed claims

#1402 is a verified rollback reference,35,755,833,859 compressed bytes and about
75.6GB of archived workspace. Its156 compiled scope is not a158 resume scope.
A physical migration experiment must separately budget download/extraction/disk,
verify the old input, discard old completion and regenerate the158 graph.
Siso/BuildBuddy action-key reuse is the first supported reuse path; actual hit
rates and time savings must be collected from the new run, not inferred from
unchanged source counts. No measured upgrade compilation saving is claimed yet.

### Signing reference recovered

The actual #1402 `apk-signature.txt` was independently read back:
https://output.circle-artifacts.com/output/job/b616cd03-c38e-40b6-acc7-a20919fba57a/artifacts/0/brave-apk/apk-signature.txt

Its sole signer certificate SHA256 is
`32a2fc74d731105859e5a85df16d95f102d85b22099b8064c5d8915c61dad1e0`.
The new APK acceptance wrapper now requires this exact certificate as well as
valid signature, package, ARM64 payload and other audits. Four local gate tests
pass, including foreign-certificate rejection. This checks certificate parity;
versionCode compatibility and actual install-over/device behavior remain pending.
