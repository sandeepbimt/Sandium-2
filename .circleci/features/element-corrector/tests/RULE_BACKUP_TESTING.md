# Rule backup native interface

Normal-profile-only `SandiumElementColorsUtils.exportRules(Profile)` returns the
raw origin dictionary as JSON, `{}` when there are no saved rules, or an empty
string on denial/invalid existing data/size overflow. The Java manager supplies
the versioned file envelope. Call from the UI thread.

`importRules(Profile, String rawOriginDictionaryJson, boolean apply)` returns
`{ok, added, conflicts, duplicates, error}`. `apply=false` previews only;
`apply=true` revalidates the current store before merging. Existing same-target
and property rules win; exact duplicates are skipped. No removal or replacement
is implicit. Empty inputs and invalid/over-limit input leave all preferences
untouched. A successful apply uses one preference dictionary replacement and
requests a pending disk write. That is not a synchronous disk-durability promise.

Limits: 8 MiB UTF-8 native JSON input and merged serialization, 128 exact
canonical HTTP(S) origins, 32 rules per origin, and the existing native descriptor
bounds. Unknown fields and invalid descriptors are rejected. Private profiles
cannot export or restore, even if called directly through JNI. Restore affects
future navigation/reload, not live renderer node bindings. No URLs are fetched.

Verification:
- `python tests/test_rule_backup.py`: real production store implementation compiled
  and exercised with narrow Chromium/pref/origin/parser API stubs. Covers dry run,
  apply, deduplication, conflict retention, input/projected caps, multi-site
  no-partial-write behavior, private/no-pref rejection and malformed existing
  storage. It does not test Chromium's JSON parser, origin canonicalizer, actual
  preference durability, JNI, or device behavior.
- `python tests/test_json_reader_compile.py`: pinned JSONReader declaration
  compatibility; parser behavior is not simulated as proof.
- `bash android/tests/run.sh`: chooser/wrapper Java compile and stub lifecycle
  tests. Existing dark gate test stubs were completed (Tab.getUrl and
  SandiumDarkPages.enabled) so this pre-existing source dependency compiles.

A native Android build plus device round-trip restore remains required before
claiming end-to-end verification.

## Android manager candidate

Appearance > Element color corrections replaces the duplicate Dark page defaults
dialog and exposes only color-rule view/download/restore. Settings > Sandium Shields
> Custom blocking rules sits next to Content filtering and exposes only ad/element-
blocking view/download/restore. Content filtering and its existing editor remain
untouched. Each screen rejects file-result request codes from the other category.
Night Mode continues to own global dark policy; Shields retains the site switch.
Downloaded filter subscriptions are not treated as custom rules.

Each category uses its own version-1 `sandium-rules` JSON backup, selected via Android
ACTION_CREATE_DOCUMENT/ACTION_OPEN_DOCUMENT (no broad storage permission and no
implicit upload). Color restore previews added/conflicting/duplicate counts, keeps
existing conflicts, and calls the native all-or-nothing merge only after confirmation.
Ad restore warns that the backup must be trusted and appends the original imported
text intact using a synchronous native UI-sequence read/append/write after confirmation.
This avoids overwriting another window's edits between asynchronous get/update calls. It doesn't rewrite/deduplicate
individual lines because directive blocks/comments can carry meaning. Immediate
re-import of the same appended block is a no-op. Other overlapping backup blocks may
contain duplicate filters; original text is never removed. Both stores remain separate,
so there is no cross-store atomicity claim. Restored colors require page reload.

The manager is unavailable to private profiles. Private color corrections are never
exported. The existing ad provider is global, so backups are explicitly labeled
browser-wide rather than falsely promising private-profile separation.

`android/tests/test_rules_manager.py` compiles the production Java manager/codec with
narrow Android/Chromium/JSON API stubs and exercises eight real lossless-ad-merge and
UTF-8 size-limit assertions. JSON parsing itself and Android activity/document-picker,
Mojo callbacks, JNI-generated bindings and process-restart flows require APK tests;
they are not certified by these host checks. `tests/test_saved_rules.py` includes both
new host harnesses in the active product suite.

Required device QA before acceptance: empty/populated view; export/readback both
categories; import wrong category/version/invalid UTF-8/oversized file; cancel picker
and cancel confirmation; merge conflicts/caps; duplicate imports; document provider
read/write failure; rotate/background/reopen during picker; private profile denial;
close/reopen browser and confirm persisted rules still apply; ensure ad import actually
reloads filters and no previous rules disappear. Also verify Appearance link survives
release shrinking and every row is usable in Settings.

Placement tests instantiate both actual Java screens with host API stubs and inspect
the created row titles, plus exercise category request-code ownership. XML/source
checks verify the existing Content filtering link remains, the new row is adjacent,
and explicit preference ordering places it inside Shields globals, not at the end
of privacy settings. Device screenshots remain necessary for visual acceptance.
