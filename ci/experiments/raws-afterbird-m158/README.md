# RawS + Afterbird: isolated M158 extensions preflight

This is the first source slice, not an APK. It keeps Chromium M158, RawS native blocking, Chromium's install and permission UI, and the stock Manifest V2 admission policy. Only the Desktop Android build graph, two legacy toolbar API schemas, and the phone extension-menu fallback are prepared. The regular-profile manager is used when the phone has no popup coordinator; the existing desktop menu path is preserved.

## Reproduce

1. Use a new, disposable Chromium checkout at the revision in `inputs.json`, with the exact #1537 RawS overlay already applied.
2. Use the original `ci/args.gn` from the pinned RawS checkout. Run `python3 prepare.py --source <chromium> --raws-args <raws>/ci/args.gn` first. It makes no file changes.
3. On the same isolated checkout, pass `--apply` to apply the two reviewed file changes and write args to `out/RawSAfterbirdM158`. Do not copy those args into a regular build; the Desktop Android graph may need a fresh cache and separate CI capacity.
4. On a provisioned Android builder run GN generation for that output before any compile. Confirm `is_desktop_android=true`, `enable_desktop_android_extensions=true`, `enable_extensions_core=true`, and ordinary desktop-only `enable_extensions=false`. Do not publish or use the official signing context.
5. Because this slice deliberately retains the RawS app ID to exercise its real UI, install only in a disposable Android emulator or dedicated test profile/device with no daily-use RawS installation or data. Android signing compatibility is not assumed.

## Acceptance

- Open and close Extensions on a phone, as well as a tablet/desktop-size layout. No null-coordinator crash. Verify install prompts, cancel/deny, launch, disable, uninstall, and persistence of the user choice after restart.
- Use a benign, publisher-controlled MV3 probe with minimal permissions on a local test page, then optionally uBlock Origin Lite. Do not infer a functioning engine from the presence of a menu.
- Full uBlock Origin is a separate MV2 test. Afterbird's M151 policy patch affected all MV2 extensions; it is deliberately not copied. At pinned M158 the initial version check has manifest version, type and location, but no verified publisher identity. A targeted experiment must preserve prior policy/permission checks and use a separately reviewed trustworthy install path. Do not accept a ZIP hash alone as publisher verification, treat unrelated extensions as components, or use a promptless unpacked path.
- With permission to run the classic extension and a verified build, test known blockable requests on a controlled page with only one blocker active. Verify successful and denied network requests, one cosmetic rule, and both enabled and disabled persistence across process restart. No full MV2 or uBlock success is claimed at this stage.

Reference: Afterbird v1.9.1 (exact commit in `inputs.json`), `patches/m151/0002-browseraction-schema-desktop-android.patch` and `0003-extensions-menu-null-coordinator-fallback.patch`. Source changes are adapted to RawS M158, not a wholesale donor import.
