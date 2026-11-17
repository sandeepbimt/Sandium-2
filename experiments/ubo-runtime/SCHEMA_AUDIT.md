# Pinned Android schema audit after job 1319

Job 1319 compiled `extensions/common:common` with extension core enabled, but
failed three translation units on missing `extensions/common/api/scripts_internal.h`.
Pinned Chromium d331de35ca8ab1358c7a17e4bd41627d55eaef51 has the three consumers
unconditionally in `extensions/common/BUILD.gn`, and common depends on
`//extensions/common/api`. That target publicly depends on `generated_api_types`.
The dependency edge exists; the schema input does not.

`extensions/common/api/schema.gni` previously selected scripts_internal.webidl
only for enable_extensions or enable_desktop_android_extensions. Mobile EXT0
sets neither, only enable_extensions_core. Move this types-only schema to the
shared list and remove the two old conditional entries. This preserves one copy
in desktop/desktop-Android and adds the missing mobile-core types, without
turning on desktop APIs. Its external types (RunAt, ExecutionWorld) come from
extension_types.json, already shared.

A second concrete MV2 input omission exists: chrome/common/extensions/api/
api_sources.gni selects browser_action.json and page_action.json only under
enable_extensions. Move those uncompiled binding schemas to the shared list.
uBO's manifest declares browser_action. No desktop private API batch is enabled.

Initial required namespace input audit:
- alarms, storage, runtime, i18n, webRequest: shared extension API schemas.
- tabs, windows, webNavigation, contextMenus: shared Chrome API schemas.
- content_scripts and extension_types: shared types-only schemas.
- web_request_internal: shared uncompiled sources.
- privacy implementation: preference target is core-enabled and its dependency
  is present in Chrome API BUILD; complete privacy JS-schema registration and
  runtime feature availability still need validation.

This is exact source input/dependency analysis, not a successful native compile
or proof of runtime API functionality. Other private desktop-only schemas remain
guarded. Re-run Full to establish compiler results; do not distribute as verified
engine replacement merely because compilation succeeds.
