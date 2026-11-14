# Sandium quick motion: source-reviewed scope

Policy: alpha-only 120ms content entry/navigation, zero input delay, no spring/bounce/scale, no changes to web navigation, Shields logo/tracer, preference values, or native toggle thumb animations. Platform ValueAnimator duration scale/disabled state is honored; no override of accessibility preferences.

Implemented:
- Custom phone menu popup uses existing Chromium PopupWindowAnimFade instead of anchored menu zoom/slide; low-end and disabled-animator cases remain immediate. Native dismissal/back/outside-tap unchanged. This existing window resource has platform-controlled timing, not the content 120ms constant.
- Paged/all/editor navigation gets a 120ms linear alpha entry. Only child content fades, leaving the sheet background opaque. Background model refresh replaces the animation target but retains the same running progress; drag reorders do not retrigger fades. Detach cancels/reset alpha. Native complex-action fallback remains native.
- BraveSettingsActivity existing fragment lifecycle callback fades newly created top-level settings fragment content once; nested fragments avoid double fades. Stale/detached/destroyed callbacks restore alpha instead of hiding content. Existing navigation/fragment animations are not globally overridden.
- Welcome content over a stable opaque root and expanded advanced options fade in. Collapse remains immediate to avoid delayed layout/input. Native switches retain native state transitions. Destroy resets/cancels owned entry animations.

Not a universal animation guarantee: OS permission/file-picker/share-sheet/IME UI is system-owned; feature-owned dialogs, WebUI, Shields popup, Settings exits, native complex menu hierarchy and dynamically revealed preference rows have not been converted or device-verified. Existing native animations may still apply. Do not impose blanket LayoutTransition on preference trees: it can animate asynchronous adapter updates, flicker state, disrupt scrolling/focus and cost frames. Broader coverage needs explicit surface-level audit.

Validation: pinned Settings callback exact-anchor/idempotency/drift tests; menu composition applied twice to pinned AppMenu/handler and Brave fixtures; theme tests; five motion source-contract tests. No APK compilation or device frame/input/accessibility validation performed. Check native app transitions at animator scales 0/1, rapid back/editor switches, preference navigation, TalkBack and lower-end devices before declaring runtime success.
