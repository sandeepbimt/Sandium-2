# Repeated menu persistence report after #1221

#1221 contained completed-edit disk writes. Its predecessor explanation (only Done
saved) is therefore insufficient to explain the repeated user report.

Investigation found no loss in parser/serialization, resource-name identity or catalog
reconciliation. Unavailable actions remain remembered; newly available actions append.
The overlay verifies installed Java byte-for-byte, so a stale presenter-copy path was
not found. AppMenu.show constructs a new presenter rather than reusing a stale snapshot.

One inconsistent boundary remained: load used the passed popup/activity context, while
save used application context. This change routes both through exactly one application
SharedPreferences handle and migrates a legacy contextual value only when canonical
storage has no value. The original file/key/version are retained.

The actual new SandiumMenuPreferences Java implementation is tested against a file-backed
SharedPreferences stand-in across separate JVM processes. Tests exercise distinct popup
and application namespaces, migration, edit/save/read, hidden state and order, separate
storage, stale-legacy non-overwrite, and failed writes. Presenter source tests enforce
that reads and writes use this same store. Existing tests cover explicit Cancel,
completed edit saves, catalog changes and state restart behavior.

This eliminates a potential namespace mismatch. We have NOT proven that the user's
Android contexts actually resolve different files, nor reproduced their #1221 failure
on Android. No native Android/device result is claimed. APK validation must change menu
ordering and visibility, press Done, fully close/reopen, then repeat with Exit and
force-stop. A continued failure requires runtime preference inspection/logs; it must
not be described as a confirmed root-cause fix solely on these host tests.
