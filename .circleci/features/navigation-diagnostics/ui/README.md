# Local diagnostic controls

The native Settings > Navigation diagnostics entry uses the existing preference
styling and Nala bar-chart icon. It exposes Start, Stop, Mark unwanted ad or
warning, Export and Clear. The recorder remains off until explicitly started.
Start replaces the preceding app-private saved session; Clear stops and erases it.

The UI consumes the SandiumNavigationDiagnostics static API:
start(): boolean; stop()/clear()/markAdWarning(): void;
isRecording(): boolean; snapshotJson()/snapshotSummary(): String.
Recorder owns the two-minute/5,000-event bounds, typed privacy allowlist,
private-tab exclusion at every producer, and session expiry. UI also gates
actions on initialized, non-shutdown, non-private profile. It does not infer
ad or warning detection from page content.

Export stops and snapshots before opening ACTION_CREATE_DOCUMENT. Only the
returned content URI is accepted; no storage or persistent URI permission is
requested. A background worker writes UTF-8 JSON to that selected destination.
Cancellation retains the recording. Recreated/destroyed screens discard pending
export bytes rather than persisting them in state. Interrupted/failed writes
report that a partial file may remain. Export does not erase the recording,
upload automatically, or log exception details/URIs.

apply-ui.py composes only the UI source, its source-list entry and main-settings
entry. Recorder integration must run it after resetting source inputs and verify
the outputs in the final consumer phase. It is deliberately not independently
wired into a pipeline before the recorder exists.

Tests execute extracted production export methods against Java collaborators:
cancel, missing/invalid URI, private state at return, success, duplicate result,
writer failure, absent chooser and destroyed state. Source tests cover lifecycle,
no storage permissions, replay idempotence and unchanged neighboring settings.
These are not Android instrumentation tests. Real chooser, rotation, dark/light
rendering and end-to-end event coverage still require a later authorized device
build. No CI or Android build was started.

Capture/restore follow-on: SandiumDiagnosticsCapture.install initializes the
recorder under the Android no-backup private directory, then registers a static
observer with no retained Activity, tab or view. Called by settings creation,
Start, and the TabWebContentsObserver factory before construction for cold tab initialization.
Recorder initialize(File directory) must be idempotent. The JNI initialization
owner must use this same directory for events arriving before a tab observer.
The native tab observer source now belongs in reset/final consumer inventories.

UI now describes app-private saved sessions, original expiry, abrupt-kill loss
of unsaved events and status after reopen. Core recorder owns restore validation,
torn-write recovery, durable clear, reboot detection and storage-error reporting.
These claims require that persistence implementation at integration; this UI
change alone does not make an in-memory recorder durable.

The capture bootstrap is compiled/executed against narrow declared-interface
stubs: regular capture,16/11 payload arity, zero/unlinked nav ID, stopped recorder,
private/incognito tab, destroyed tab, shutdown/uninitialized/missing profile.
This validates UI-side logic, not real Android GN dependency resolution or
device compositor rendering.
