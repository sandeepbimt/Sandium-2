# Dormant CompositorView native adapter

The complete candidate planner includes `native_adapter.py` behind the explicit experimental
profile; no GN or generated JNI build was run. It transforms exact pinned native CompositorView.h/.cc only.
The Java counterpart and layout hook are separate candidate modules. No holder
lease acquisition, view retention, input/a11y suppression or real phone effect
is provided by this native adapter alone.

Begin consumes positive monotonically increasing tokens, rejects active sessions,
unready/paused/overlay surfaces and pending navigation, captures a committed
content-owned target and constructs the observer without external callbacks.
False transfers no ownership. Completion clears token/WC/owner before Java and
performs no later member access. The owner expressly supports deleting itself
from its moved completion callback. Destructor is silent; Java holder teardown
must independently dispose its native-page lease.

A scene query calls Java for current eligibility, checks the adapter WeakPtr and
token after that potentially reentrant call, resolves SceneLayer from Java afresh
and rejects its zero native pointer. It compares the currently selected refcounted
layer and direct compositor-root parent, never dereferences cached raw SceneLayer.
Scene destruction does not detach its refcounted layer, so ancestry alone is not
accepted. Java must independently query current layout/Tab/WC/window/holder gates.

Finalization invokes the observer only after ResourceManager frame updates and
as the last action. The pinned slim compositor consumes next-frame callbacks when
generating that frame; successful callbacks may retry on later frames. This is
why the observer revalidates target/metadata/scene at delivery. Neither adapter
claims an Android native-view atomic transaction or complete content visibility.

Native surface create/destroy/change/recreation, window, tab, scene, draw-pause,
overlay, physical-backing/controls-resize/keyboard changes revoke conservatively.
Some repeated geometry setter calls can therefore abort an otherwise safe lease;
this is deliberate fail-closed behavior until real lifecycle integration is tested.
There is no extra timer or continued retention on a failed readiness condition.
The caller must request a compositor frame after successful begin, and must own
the bounded existing lease deadline and all unhandled security/holder changes.

Boundary revocation clears state synchronously but posts a WEAK native notification.
Synchronous Java completion at a mutation prefix could destroy CompositorView and
leave the remaining original method using freed memory. Posting avoids that UAF;
stale notification tokens are rejected by Java. Destruction cancels weak posts.
Explicit Java cancellation already clears its state and performs holder cleanup.

Tests compile the EXACT new native method bodies with explicit weak-pointer,
observer, JNI and task-runner doubles using ASAN/UBSAN (LeakSanitizer disabled,
unsupported under this environment's ptrace). They cover callback reentry, same-
process destruction, stale/reused tokens, fresh scene/nativeptr/ancestry checks,
and deferred notification after replacement/destruction. These doubles do NOT
prove Chromium callback-template, GN or generated-JNI compilation. Full exact
source transforms/replay and combined Java/native/layout source ordering are
checked separately. No Android build, CI run or device validation is claimed.
