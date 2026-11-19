# Full Mode-U: Brave 1.100.58 / Chromium 158

Status: locally admitted for a fresh Full Mode-U run, pending parent publication and service processing. No target CI run or publication yet.

## Verified upstream

The latest official GitHub stable release v1.100.58 includes Android artifacts.
The signed core tag resolves to bd6d26d1bced03c17a98baa86d2cd3425d543d1b;
its immutable package.json selects Chromium 158.0.8127.42, commit
52bdd21723d5db0c9ab11716d38feac74828cf84. Wrapper commit
9a51201f8a71f3f2bd377322aaa09c9742588cdd selects that core. The older
Brave.com Android notes are not evidence of the newest GitHub Android release.

Official release packaging comparison: BraveMonoarm64.apk 366784853 bytes
(~349.8 MiB), Bravearm64Universal.apk 213076728 bytes (~203.2 MiB).
These are different packaging targets. This candidate retains the established
standalone Mono target until Universal dependencies/signing/install behavior are
positively verified. No 200 MB APK promise or feature-stripping shortcut.

## Frozen requirements to preserve and revalidate

- All retained Sandium features and 13 reviewed Brave feature-group removals.
- #1389 single-handoff architecture and later capture-coordinate fix; Chromium
  rendering foundation, WebKit-inspired lifecycle design, not a WebKit engine.
- Native Chromium blur Off/On only, welcome default On. No Sandium blur-strength
  parameters or custom timed blur manager. Preserve separate darken control.
- Off-white progress on the address bar's top line, not whole green address fill.
- Latest approved welcome: grey disabled animated dots; off-white ready action
  Quick Restart or Start browsing; pale green 1.5-second fill and matching
  Restarting/Starting 5-to-1 countdown. Android string resources, no lint bypass.
- App notification choice default On; request OS permission only after setup /
  restart and homepage, never during welcome. Preserve denial/no-repeat behavior.
- Official release ARM64, compatible signing, validated APK followed by full
  archive upload/readback/fresh restore, even if APK is produced early.

## Recovery and validation boundaries

The environment reset removed unpublished 157-upgrade worktrees and their local
commits. Their previous test results are historical, not validation of this 158
candidate. Recover actual code if available; otherwise reconstruct with explicit
review. Start from verified #1402 source/reference, preserving rollback.

The #1402 archive is Chromium 156/Brave 1.98.62. It is NOT a compatible compiled
checkpoint for this target. New U identity must separate source acquisition,
source readiness, feature preparation, GN graph readiness and accepted APK.
A source-only seed may be considered only with explicit verification and old
output invalidation; never relabel old completion proof.

Whole-job timing includes restore, source sync, preparation, compile, archive,
upload and verification. Reserve conservative measured archive capacity and
stop compilation safely before deadline; distinguish budget expiry from real
build errors. Checkpoint consistent progress before crossing runs. Ordinary
Full pipeline and RawS remain unchanged by this preparation.

## Not yet validated

158 overlay composition, GN generation, official build, lint, APK device
behavior, remote continuation and newly generated archive promotion. Candidate
profile remains ready=false until required prelaunch reviews pass.

## Packaging follow-up (not enabled)

Pinned Brave build/android/BUILD.gn defines
`//brave/build/android:sign_app_convert_aab_to_apk` when
`target_android_output_format=aab`. It builds/signs chrome_public_bundle and
converts ChromePublic.aab with bundletool to Bravearm64Universal.apk. That is a
separate packaging path, not a size guarantee from is_official_build alone.
Before adopting it, verify package ID, certificate, ARM64 ABI contents,
standalone install/upgrade behavior and feature parity against the Mono artifact.

## Historical local integration checkpoint (19 November)

The following is the earlier checkpoint; the final activation below supersedes its open local source-preparation blockers.

Integrated source and fixture checks, not a built APK:

| Area | Evidence | Remaining gate |
| --- | --- | --- |
| Welcome controls | 14 tests including executable preference/countdown behavior | Android compile and device lifecycle |
| Native blur and single handoff | 87 of 88 single-handoff tests pass; remaining failure is inherited historical CI-config equality | Final full target composition, Android/native compilation and device behavior |
| Address progress | 10 feature tests; exact upstream158 anchor/replay checks | Native rendering on device |
| Deferred notifications | Exact Chromium158 plus Brave coordinator patch replay | Final composition verifier, Java/NullAway and permission lifecycle review |
| Playlist/Billing/News | Exact158 replay, idempotence and native feature-map tests | Remaining removal groups and complete product replay |
| Lint | Six target-policy tests; exact upstream158 rules retained with zero additional exceptions | Actual target lint output and evidence-backed resource review |
| Source/host setup | Exact source receipt, owned tree, verified Node/pnpm digest checks | Actual network initialization and interrupted continuation |
| Checkpoint phases | Local tar/zstd fresh-copy restore, process cancellation and verifier-boundary tests | Production workflow and remote readback/recovery proof |

The broad baseline is itself not green: exact pre-upgrade a672821 ran 610 tests
with 33 failures and 14 errors. The earlier candidate run at be19827 ran 647
with 38 failures and 27 errors. Named diagnostics were compared rather than
attributing all historical failures to this upgrade. The five new navigation
fixture failures have since been corrected using exact158 inputs; no runtime
navigation gate was weakened. Old lint inventory provenance continues to fail
closed when called outside its original156 scope.

A key preparation blocker is the legacy prepare-brave-source.sh: it combines
156-specific sync/pin checks, host installation, product transforms and GN.
Full-U must use separate owned source acquisition and a reviewed target-specific
product adapter, not invoke that legacy script or activate a readiness boolean.
Workers are reviewing the exact reset payload and compiler/remote-execution/GN
pieces independently before assembling the adapter.

No target source compile, APK, uploaded archive, or speed improvement has yet
been demonstrated. Ready remains false; no publication or run was started.

## Latest execution decision

Sandeep explicitly chose a **fresh first Full Mode-U run**. Do not restore or
physically migrate #1402 for this run; preserve it unchanged as rollback.
Existing content-keyed Siso/BuildBuddy action-cache reuse is allowed, without a
hit-rate promise. Subsequent U stages and runs restore only newly verified,
exact-target compatible U checkpoints. Full archive after APK remains mandatory.

Actual local official host bootstrap exposed a pnpm11 packaging dependency on
adjacent dist/pnpm.mjs. The installer now preserves the complete authenticated
pnpm payload rather than copying its executable alone. A real download/install
passed for pinned Node24.16.0 and pnpm11.11.0 after this correction; no system-wide
Node/package-manager configuration was changed and no CI run was used.

## Final local activation

The target profile is ready=true only after complete exact158 product composition,
canonical reset/replay, interruption recovery and exact nested rollback passed.
The target-specific product adapter has replaced the old156 preparation path.
This admits execution, not a claim of an APK or successful target GN generation.

First run is fresh: branch work/full-u-1100 in both CircleCI selectors, workflow
Full-Mode-U, run_full_u=true, full_u_resume=none, full_u_recover=none,
run_build=false, run_maintenance=false. All run defaults remain off. No1402
restore or migration is allowed. Preserve that checkpoint as rollback.

Each phase still requires actual source identity, resolved official ARM64 GN and
product proofs before progression. The signer must match the recorded1402
certificate. Full archive, exact readback and fresh verification precede final
completion. Source-only recovered state never claims an APK or compiled readiness.
Conservative disk/time admission can stop with a resource hold rather than risk
losing the prior verified checkpoint. Cancellation/platform death cannot guarantee
a new checkpoint.

Keep upstream brave target scheduling including required lint. Optional lint
reordering is deliberately excluded from this launch. No blanket lint suppression
and no separate lint pre-test job were added. Actual158 GN, lint, compilation, APK
and remote archive transport remain runtime validation, not local test claims.
CircleCI service processing remains unverified until the explicit launch.

Final activation regression commands (all passed locally):
- `python3 -m unittest discover -s tests -p 'test_upgrade1100*.py'`: 48 tests.
- `python3 -m unittest discover -s tests -p 'test_full_u*.py'`: 41 tests.
- `python3 -m unittest discover -s .circleci/original-full -p 'test_*.py'`: 56 tests.
- `git diff --check`: clean. YAML parsed; three run defaults false, both
  receipt parameters none. Negative ready/branch gates remain tested.
