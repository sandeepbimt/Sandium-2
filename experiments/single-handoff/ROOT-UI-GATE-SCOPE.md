# Dormant root UI safety predicate

`ui_gate.py` adds a read-only RootUiCoordinator predicate and marks it permanently
ineligible at the beginning of RootUiCoordinator teardown. The complete source
planner includes it behind the explicit experimental profile.

The exact pinned APIs provide live tab/toolbar obscuring tokens, modal presenter
visibility, bottom-sheet current and target states, scrim visibility and app-menu
visibility. Missing initialization fails closed. A peeked, moving or expanding
sheet does not qualify merely because `isSheetOpen()` would return false. Both
current HIDDEN and target HIDDEN/NONE, and no hiding transition, are required.

This predicate is not a universal Android window/occlusion detector. The holder
must independently validate its current tab, native resource, selected layout,
window attachment/focus, visible children, geometry, keyboard, input, accessibility
and security lifecycle. It must revoke before drawing if eligibility changes and
must re-query at presentation delivery. No observer notification is treated as
proof that all other overlays are absent.

The root method does not preserve old web content or alter security/URL ownership.
Its source and compiled-host tests cover only the stated query/lifecycle contract,
including a negative regression that rejects a permissive peek-sheet policy.
Actual Android/GN/JNI compilation and device behavior remain unverified.
