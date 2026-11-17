# Capture-origin diagnostics (HELD; not wired)

Purpose: explain measured native-home preview/live displacement, not hide it.
No control positioning, bitmap pixels, timing, cache policy or animation changes.
No URL, title, text, image content, account identifiers or persistent identifiers are logged.

Java sample stages: 1 hardware capture callback, 2 synchronous fullscreen capture,
3 software capture. Each records a process-local sequence, monotonic uptime,
window/local origin, attachment, height, scroll/padding, view matrices, native
controls overlap and the supplied synchronous padding. Detached window positions
must NOT be treated as current screen coordinates.
Native `SandiumBlurOrigin` records the newly inserted blur layer's ancestor chain;
`SandiumBackParentOrigin` records the parent chain before inserting Back layers.
Each records up to 16 local positions and transform matrices; these are not
already-composed window coordinates. Trace capture timestamps and the existing
native capture/Back request sequence events provide correlation with Java log
samples. There is **not yet a shared Java/C++ capture ID**; asynchronous callbacks
must be disambiguated with existing request events, and ambiguous samples rejected.

Candidate invocation only: `python experiments/capture-origin/apply.py SRC --apply`.
The plan validates all three files before any write. No production wrapper or
reset manifest was changed. To use in a future approved diagnostic APK, wire after
navigation overlays, own/reset the pinned NativePageBitmapCapturer source, and run
full pinned source composition + Android/C++ compilation first. Current standalone
script is deliberately not a shipping feature.

Evidence needed in one controlled navigation: record screen plus navigation trace
and numeric logcat; compare same-capture origin at source, insertion, and restored
live page. Test home→URL, home→search, Back→home; keyboard shown/hidden; top/bottom
controls; software/hardware capture; canceled Back; detached native page.
Derive offsets from measured transforms, never the observed fixed 112px.

Host tests: pinned-source anchors/replay and all-before-write failure test pass;
C++ ancestor-walk stub compilation passes. Java helper execution test is currently
SKIPPED because this workspace has a JRE but no javac. Neither host doubles nor
lexical transforms establish actual Android/compositor behavior.

Pinned Java fixture is fetched unmodified at Chromium
`d331de35ca8ab1358c7a17e4bd41627d55eaef51`, path named in apply.py.
