# Held numeric browser/Android transport

This is a transport, not a statement of completed event coverage. No production
wrapper, reset manifest, build trigger, producer, renderer Mojo message or ad
engine has been enabled here.

Boundary: content's public ContentBrowserClient virtual API -> Chrome Android
implementation -> existing night_mode::WebContentsThemeClient generated JNI ->
recorder. No dependency from content onto chrome implementation classes. Recorder
source goes into existing night_mode:java target (the same architecture used by
page-text settings); namespace remains chrome.browser.sandium.diagnostics.

Public API:
- IsSandiumNavigationDiagnosticsEnabled(WebContents*) -> bool
- GetSandiumNavigationDiagnosticsEpoch(WebContents*) -> int64 (0 when disabled)
- RecordSandiumNavigationDiagnosticForEpoch(WebContents*, int64 expected_epoch,
  int event_code, int64 navigation_id, int64 source_ticks_us, const vector<double>&)
- RecordSandiumNavigationDiagnostic(WebContents*, int event_code,
  int64_t navigation_id, int64_t source_ticks_us, const vector<double>& values)

Caller samples browser TimeTicks at the source event. Java stores it separately
from its receive timestamp; these are not presumed identical clock domains. The
original NavigationHandle::GetNavigationId matches Java getNavigationId and the
recorder remaps it to a session-local ID. A zero ID is explicitly unlinked, not
an invented match. Event integers and exact numeric-field shapes are centrally
validated by the recorder; transport accepts no text.

Chrome rejects non-UI calls BEFORE dereferencing WebContents, null contexts,
actual BrowserContext off-the-record status, recording disabled, >16 fields, and
negative identifiers/timestamps. The Java facade rechecks Profile off-the-record
status; recorder validates finite numbers and exact event schema. Content's
non-Chrome default is disabled/no-op. Java/C++ calls are synchronous; there is no
retained pointer or pending task.

Background/IO producers MUST NOT use this API by passing raw WebContents across
threads. Safe async delivery requires lifetime management and the recording-session
epoch captured with the event on UI, rechecked by the ForEpoch variant on delivery.
Epoch transport and Java validation are implemented; asynchronous producer
lifetime/dispatch code is NOT. Capture an epoch once at source, never query a fresh
epoch when an old callback arrives. Producers should check enabled before allocating
numeric vectors. Existing synchronous API is for same-call-stack producers only. Missing context/global ad-service events cannot be
claimed private-safe; their ownership still needs review. Renderer event transport
also remains absent, so browser-side policy cannot be called first rendered paint.

Integration: union both reset lists in integration-plan.json, generate the recorder
source, apply after existing Dark/Page Text apply+verify, then verify bridge output.
Existing JNI target already scans WebContentsThemeClient.java. Own reset/replay
must restore pristine sources before earlier exact-anchor overlays; the standalone
plan validates every owner before writing. Preserve source fixtures and later
consumers. Need full JNI generation, Android/C++ compilation and device lifecycle
checks before shipping.

Validation completed: four tests (pinned anchors/idempotence/privacy syntax, actual
inserted Chrome gating bodies compiled with strict g++, actual Java facade methods
executed via ECJ host stubs, final-owner fail-closed/no writes). Plan also succeeds
against actual composed #1315 Dark+Page Text source; all owner transforms replay
idempotently. Host collaborators do not replace native Android/JNI compilation.

Follow-on validation: actual current recorder compiled together with inserted Java
facade bodies; native timestamp preserved, stop/restart stale-epoch rejected, private
context rejected. Nine-owner plan validated on composed #1315 source without writes.
