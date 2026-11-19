# UI158 source admission audit

Target Brave core `bd6d26d1bced03c17a98baa86d2cd3425d543d1b`, Chromium `52bdd21723d5db0c9ab11716d38feac74828cf84`.

`ui158-guards.json.gz` contains 55 exact source/patch inputs. Every byte was checked against the corresponding official repository Git-tree blob ID before packaging. Each entry records Git blob and SHA256. The test executes six applicable Brave patches with `git apply`; other reset patches concern files outside these ten UI overlays and are not represented as validated here.

Coverage: Shields popup, bottom toolbar, paged menu, search choices, focus follow, settings fade, progress diagnostics, suggestion anchor, home shortcuts and video gestures. Their source guards now require the exact target pins. Real prerequisite transformations are invoked for menu removal policy, unified address position routing and settings motion. Each component is applied, read back and reapplied immediately in production-relative order. New drift cases reject unknown toolbar/menu anchor changes.

Reviewed upstream drift:
- ToolbarPhone now uses `mIsToolbarUiRefactorEnabled` to hide Home and a nullable local tab-switcher coordinator. The existing Sandium forward-slot policy is retained; the nullable native coordinator branch is preserved.
- CustomizeBraveMenu's comment/skip clause now includes site controls. Insert before the exact new comment and preserve the native `info_menu_id` clause.

This is source-subset validation, not the complete removal/product pipeline, GN reachability, Android/NullAway compilation or phone behavior. Git HEAD lookup is mocked solely for the fixture subset; bytes and patch application are real. The canonical reset remains required before whole-pipeline replay: later BUILD.gn inserts can interrupt an earlier owner's adjacency anchor (notably video after home). The test does not claim arbitrary reordering/reapplication across such owners is safe.
