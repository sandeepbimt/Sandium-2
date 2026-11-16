# Menu persistence, 16 November 2026

User report: menu customizations disappeared after closing and reopening Sandium.

Identified source loss path: the editor only serialized its draft when Done was pressed.
Closing the popup or browser while editing discarded all completed reorders/removals.
Done used asynchronous SharedPreferences.apply(), without a disk acknowledgement.
No device trace demonstrates that correctly Done-saved settings were independently lost.

Every completed reorder, hide, re-add, and confirmed reset now saves the same versioned
layout before rendering. Back, outside dismissal, and closing the browser retain these
completed edits. Explicit Cancel restores the snapshot from editor entry. A drag that is
cancelled or dropped outside a target does not change the saved layout.

Small bounded user-initiated writes use SharedPreferences.commit() with a restored
StrictMode allowance. A failed disk acknowledgement reports an error and retains the
last confirmed layout in the editor. No writes run during scroll or drag movement.
The preference namespace and stable resource-name IDs are unchanged, so existing saved
layouts migrate without resetting, and conditional catalog entries remain remembered.
Menu layout remains app-wide, as before; this does not introduce browsing-data storage.

Tests cover every edit save site, Cancel versus Back, failure handling, and serialized
state persisted through real files across separate JVM processes (hide, re-add, order,
rollback and independent storage paths). These are not Android SharedPreferences tests.
Canonical architecture tests pass. Android compilation and on-device close/reopen,
force-stop, Exit, rotation, and private/normal UI validation remain required.
