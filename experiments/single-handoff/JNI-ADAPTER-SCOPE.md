# Dormant JNI boundary work

The complete candidate planner includes the Java and native CompositorView
transforms behind the explicit experimental profile.
No GN or production JNI generation has been run. Exact injected methods compile
in host harnesses with explicit collaborators; this is not an Android build.

Java begin consumes a strictly increasing positive lease token and does not
transfer the caller's native-page resource if native begin rejects or throws.
Native begin must not invoke completion; Java also detects synchronous completion
or cancellation during begin and rejects without calling resource cleanup.
Accepted begin posts a token-guarded requestRender to the UI event queue so the
caller completes resource transfer before observation is scheduled. This is not
a cosmetic timer. Failed posting rejects the begin and cancels native ownership.

The delivery query reads current LayoutProvider/layout/tab/WebContents identity,
not a cached eligibility boolean. Pure local state (draw pause, XR/video/selection,
touch interception, attachment/focus/visibility, lifecycle and token identity) is
checked both before and AFTER arbitrary holder/layout queries. Finalized scene
and provider identity are also rechecked after these queries. Native must resolve
the current Java SceneLayer native pointer afresh; retained layer ancestry alone
cannot prove SceneLayer remains alive. A destroyed SceneLayer can leave its layer
attached in the native tree.

Completion clears Java session authority before invoking external cleanup. Explicit
cancel clears first, calls native cancel, then invokes cleanup in finally. Native
boundary cancellation must post its notification rather than synchronously call
Java while native surface/window mutation continues. Java shutdown is silent:
its holder MUST independently dispose its owned native lease during teardown.
All new Java entry points assert UI-thread confinement.

These adapters still do not acquire/retain a native page or block its input and
accessibility. The holder policy gate has no production provider yet. It must
reject modal/security/unknown overlays and geometry changes, while preserving
address-bar/Back/Cancel access. Native-page ownership must be transferred before
TabImpl destroys it, without preserving obsolete mNativePage identity or creating
a second viewport-sizing owner. Do not activate these transforms independently.
