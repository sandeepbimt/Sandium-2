# Held ad diagnostics candidate

Five real Brave source owners; no UI/pipeline/build activation. Apply after existing
engine-race/warmup/resource overlays. Requires numeric browser/JNI bridge and the
central recorder codes 10 (AD_ENGINE_LOAD), 11 (AD_DECISION), 24 (aggregate omitted).
All source transforms are staged before any write. Reset both inventories in the
integration plan. No content/browser -> chrome dependency is introduced.

## Network decisions
The original UI entry captures recording epoch, anonymous request sequence, frame
token, resource type and monotonic start time before posting the existing worker.
Only primitive data/token is copied through its existing callbacks. No WebContents
pointer is retained. Callback resolves the actual frame/WebContents again on UI;
bridge checks real off-the-record context and original recording epoch. Missing
frame/context fails closed. Private/background/orphan requests may be absent, not
labelled allowed. Existing callback/engine/control decisions are unchanged.

AD_DECISION values: request_token, phase, resource_type, blocked_by, flags_bits,
mock_redirect_present, rewrite_present, elapsed_us. Flags matched=1, exception=2,
important=4. nav ID is 0/unlinked for subresources; no guessed document association.
Duration includes queue/worker and CNAME latency, not pure engine CPU time.

Network phases: 0 primary interim awaiting CNAME, 1 primary final, 2 CNAME final,
3 no CNAME recheck final, 5 request context/initiator disappeared, 6 policy/required
metadata excluded, 7 unsupported scheme, 8 extension exemption, 9 main-document
handled by separate domain throttle. Early engine-important return is naturally
covered by the returned result. Mock/rewrite values are presence bits only.

First 512 requests per recording epoch are sampled (both template instantiations
share the budget). Every further request increments code24 aggregate omitted count
exactly once, rather than appending rows; CNAME callbacks do not consume a second
request budget. This is deliberately incomplete sampling; export must say so.

## Shared load observations (not readiness)
Four cached lanes: default/additional × DAT/filter-list. Values for code10:
engine (0 default/1 additional), load_source (0 DAT/1 list), last_result,
completion_sequence, resource_generation (-1 unknown), baseline (1 first observed).
DAT result 0 failed/1 succeeded; list result 0 loaded/1 failed/2 resources-only.
Result -1 means no completion observed. Failure does NOT prove previously active
rules are invalid; the observation sequence is NOT an active engine generation.

Baseline is sampled at first associated regular network request, NOT at pressing
Start in Settings. Subsequent request begin/result samples report changed lanes.
A load that changes while no associated request occurs can remain absent. Actual
resource generation, stale/invalid-resource dispositions, scriptlet/cosmetic
renderer acceptance and execution are NOT instrumented here. No content/rule text,
URLs, titles, DNS names or redirect payloads are recorded.

## Main-frame domain throttle
Uses real NavigationHandle ID, lifetime-owned epoch/time fields and existing weak
callbacks. Operations are distinct from subresource engine results (request_token0,
blocked_by=-1). Domain phases:10 engine allow,11 engine block,12 engine rewrite,
15 interstitial cancellation,16 already-ephemeral resume,17 enable-ephemeral request,
18 ephemeral result restart,19 ephemeral result resume,20 original cancellation+
queued restart,30 policy none,31 user proceeding bypass,32 async engine query queued.
An engine block is not claimed to mean final navigation blocked: ephemeral mode
can allow it. A queued restart is not proof the new navigation started. Destroyed
pending throttle callbacks are not inferred as a particular cancellation cause;
combine with navigation lifetime diagnostics.

## Validation and limits
Exact pinned fixtures carry SHA256 manifests. Seven focused tests cover anchors,
replay, helper execution, actual state-update snippets, epoch/private/thread gates,
shared request budget, numeric flags, failure/resources-only observations and
actual domain report ID/epoch. Existing engine-race/resource composition was also
applied before load snapshot and replays. Full transformed C++ translation units,
JNI generation, Android device behavior and overhead are not yet validated.
Disabled per-request path still resolves frame and queries the enabled JNI gate;
zero overhead is NOT claimed. This candidate does not solve all ad-warning or
fake-ad detection, automatic on-screen ad identification or popup correlation.

## Explicit recording-start baseline
`FilterListServiceFactory.captureSandiumDiagnosticLoadSnapshot(Profile, epoch)`
uses the existing Brave-owned JNI target to obtain four cached shared-engine
load observations from a validated regular Settings profile. Call after successful
recording Start; false means unavailable, not ready. The JNI response has one
browser TimeTicks timestamp plus four numeric six-field rows. Java rechecks the
epoch and private-profile status after JNI, validates finite values and exact
microsecond integer range, and sends through epoch-bound recorder acceptance.
This is a snapshot of last observed load completions, not proof of current
resources, scriptlets, cosmetic filters, or site blocking readiness. Unknowns
remain -1. Idle subsequent changes are observed only on associated requests.
The UI invocation is an integration prerequisite, not installed by this module.

The adapter adds two reset owners listed in integration-plan.json. Existing
Brave shields JNI source set already owns the factory, browser-process and
ad-block-service dependencies; no Chrome implementation depends on Brave.
Eleven focused host tests pass. Native helper bodies and Java facade bodies
are compiled against controlled collaborators; this does not replace generated
JNI or full Android/C++ compilation and device validation.
