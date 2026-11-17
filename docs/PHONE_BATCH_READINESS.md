# Phone batch readiness — 17 November 2026

This branch is the requested phone integration, not the ARM-translation or x64
emulator experiment. No emulator-only JNI guard, generated x64 configuration or
experimental independent-control geometry is imported here.

## Included source changes and limitations

1. **Grey flash:** native-home outgoing pixels now use native capture rather than
   the hidden web surface, with narrow PDF exclusion and transition diagnostics.
   This is not a general proof that all paint/compositor readiness races are fixed.
2. **Dark rendering:** gradient/shadow correction candidate is present. Google and
   other live pages still require visual validation.
3. **Address bar/page shake:** restored pinned Chromium's pre-gesture animated
   controls reveal, including repair of previously patched source. Existing locks
   and predictive Back handlers remain. This is an upstream-flow restoration,
   not verified elimination of every resize/jump. Broad new geometry stays out.
4. **Light-to-dark Back:** unmatched renderer preference policy no longer overwrites
   destination policy. Same-site/stale ordering and real visual regression remain
   to be validated.
5. **Menu:** compressed pager space, single-page indicator behavior, balanced cells
   and editor fit changes included.
6. **Redundant dark defaults:** Appearance rule manager replaces the duplicate
   dark-defaults entry; existing Night Mode remains.
7. **Saved rules:** separate color-correction and ad-block rule viewers/export/import
   in Appearance and Shields respectively. Host tests cover core codecs/merges;
   Android document-picker, lifecycle and actual reapplication still need APK QA.
8. **Legal:** small grey bottom About link preserves accessible one-tap legal info.
9. **Status bar (scope changed):** the user dropped the new cross-browser gradual
   transparency requirement on 17 November. Preserve existing status behavior.
   Matching Settings/sub-settings surface and safe Welcome initial backing remain;
   the Welcome change preserves layout/fullscreen flags and changes no geometry.
   No broad native status ownership experiment is included or required for this build.
10. **Shortcut order:** lower anchor and upward row growth included.
11. **Shortcut appearance:** no group backing, subtle shadows and site-based default
    labels included, plus requested persistent Rename.

## Additional approved assets

- Exact selected Quiet Charcoal wallpaper is included for this batch.
- Normal dark address capsule is lighter; its direct GN dependency is declared.
- Native homepage toolbar surround now shares the actual wallpaper backing.
  It is transparent only when that backing is ready, unfocused, regular-profile,
  phone/bottom-toolbar and outside transitions. Other native pages, ordinary web,
  focus/loading and unavailable-wallpaper cases retain existing safe paint.
  This is not general transparent web-content toolbar support.

## Build decision

Source-contract tests are not Android compilation or device verification. The
homepage-only surround solution preserves existing web viewport/toolbar behavior.
Cross-browser status transparency was removed from scope. User standing
authorization covers publication/build after review and integration tests; root
coordinates a single ARM phone run. No emulator work is authorized in this phase.
Actual Android compilation, visual transitions and phone validation remain pending.
