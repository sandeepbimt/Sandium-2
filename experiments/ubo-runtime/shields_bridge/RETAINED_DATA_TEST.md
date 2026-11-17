# Retained-data host regression

Run with the pinned upstream engine fixture prepared by engine-validation:

```
SANDIUM_UBO_ENGINE_FIXTURE=/tmp/ubo-engine-validation node experiments/ubo-runtime/shields_bridge/test_retained_data.mjs
SANDIUM_UBO_ENGINE_FIXTURE=/tmp/ubo-engine-validation node experiments/ubo-runtime/shields_bridge/test_retained_data.mjs --wasm
```

The test imports the production bridge, native-list reconciler and user-rule
reconciler. It reads the actual 30 configured Sandium URLs from the product
subscription script, stores native and extension settings models in temporary
JSON files, and uses the real upstream 1.76.4 static network engine. Four core
engine module hashes are checked against the fixture provenance before use.

Covered in both JavaScript and WASM modes:
- All 30 URL identities selected, with a distinct controlled blocking sentinel
  per URL; every sentinel is checked against the real engine after each stage.
- Disable one, delete another, add a custom rule; verify membership AND blocking.
- Preserve a custom exception and cosmetic-rule text (DOM hiding is not tested).
- Dispose bridge/release engine, recreate both from retained JSON settings;
  verify disabled/deleted membership, custom text and blocking survive.
- Refresh unchanged selection without recreating the deleted subscription.
- Disable all and clear custom rules, recreate again, verify blocking is absent.
- Re-enable one URL and confirm its block returns without restoring the others.
- Each successful generation requires list revision/user-text ACK; seven reloads
  occur through the production adapter, including the two reopen simulations.

This is **host-only**. Per-URL filter payloads are controlled sentinel rules, not
actual downloaded 30-list contents. Native API, vAPI persistence and compiled-list
acquisition interfaces are modelled; real filtering is executed by upstream uBO.
Reopen simulates lifecycle in one host process, not Android force-stop/reinstall.
No claim of JNI, Android SharedPreferences, installed upgrade, actual list-fetch
availability, cosmetic DOM, scriptlet, network interception or device performance
proof follows. Temporary model files are deleted; no real profile is modified.
