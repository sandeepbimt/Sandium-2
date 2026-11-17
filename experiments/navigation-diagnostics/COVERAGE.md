# Diagnostic candidate coverage (source validated, not device validated)

Recording is explicit opt-in in Settings. Start replaces the old session. Stop retains
it. Export stops and freezes a JSON snapshot before the Android document picker;
Clear deletes the private journal. No URLs, hostnames, page text, titles, filter text,
or user-entered strings are accepted by the recorder. The app-private journal is in
`getNoBackupFilesDir()`, not external storage. A private profile cannot start it;
actual producing profile/context gates also exclude private events.

## Actual event sources

| Scenario | Production observation | Important limit |
|---|---|---|
| URL/link/search/history navigation | TabWebContentsObserver navigation start, redirect, finish, browser nav ID | Does not label every UI initiation source; IDs are anonymized |
| Redirect | NavigationRequest throttle completion action and error | Observed redirect is not automatically an allowed outcome |
| Popup | RenderFrameHostImpl CreateNewWindow request and callback outcomes | Renderer-denied attempts never reaching browser absent; destroyed opener can leave unmatched attempt; child-navigation link unavailable |
| Home/native capture | NativePageBitmapCapturer actual capture-start roots, window bounds, overlap, matrix | Capture sample IDs are not fabricated links to a particular native navigation |
| Back/Forward | Existing transition state, cancellation, request tracking, activation and layer ancestry | Common completion is not always a presented frame; actual activation is separately labelled |
| Rendering | WebContentsImpl owning-document visually nonempty paint callback | Browser receipt, not GPU display timestamp |
| Dark Pages | Browser's resolved document commit policy | Not renderer-applied or visible-dark acknowledgement |
| Layout shifts | Renderer-reported layout shift batch count/scores/input attribution/timestamps for actual accepted primary-page tracker | Not cumulative CLS, not causal attribution to justification; browser receipt may follow buffered renderer events |
| Typography | Browser's resolved document policy after child inheritance | Not proof of justification/size application or layout stability |
| Ad lists | Four default/additional DAT/list last-load outcome lanes | Includes failure/resources-only results; NOT a promise of active resource/scriptlet readiness |
| Ad requests | Network callback primary/CNAME decisions and domain throttle outcomes | Only bounded first 512 requests; omitted count retained; network requests not mapped to document nav IDs |
| Unwanted ad/warning | Explicit user marker | No automated ad-warning classifier |
| Menu persistence | Presenter read/save result and rendered action order fingerprint | Canonical whitelisted numeric action IDs only; not a proven fix or complete native-settings coverage |

## Time, correlation and retention

Receive timestamps are monotonic within a process segment. A restart uses a
conservative wall-clock elapsed offset and explicit new segment; never treat it as
one continuous monotonic clock. Browser source TimeTicks are separate fields.
Navigation IDs are session-anonymized; raw IDs are not stored. After restart the raw
mapping is discarded and anonymous numbering continues. Pair process-local sample
and request tokens with their process segment. Zero navigation ID means unlinked,
not an invented association.

The total session is capped at 120 seconds and 5000 accepted events, including after
restart. A valid append-journal prefix survives tested process termination; torn
trailing records end recording with a visible recovery status. Storage failures stop
recording visibly. Header creation is synced; per-event append/close is not a
power-loss durability guarantee. Synchronous small writes can affect timings on slow
storage, so this is diagnostic mode, not a zero-overhead benchmark. Reboot detection
is not claimed by the pure-Java wall-clock scheme. Force-stop generates no events
while stopped; reopening can resume only within the original valid deadline.

## Still not proved

No full Android/JNI/Blink compile or phone runtime validation has occurred for this
candidate. These events do not by themselves prove the cause of the observed 112 px
homepage displacement, eliminate flashing, detect all advertisements, or prove
correct dark/typography rendering. Renderer application acknowledgements, complete
request-to-document/child-popup linkage, and GPU presentation remain unavailable.
