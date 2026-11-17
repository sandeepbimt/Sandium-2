# Frozen galaxy/raised homepage styling, 17 November 2026

- Approved reference: the third midnight-blue galaxy preview frozen on 17 November 2026.
- Bundled asset: `.circleci/branding/source/wallpaper.webp`, 819×1920.
- Built-in image generator edited the existing wallpaper, using the approved mockup as the midnight-blue galaxy/raised-brand style reference. Prompt required original logo/wordmark size and placement, subtle silver relief/short shadow, dark bottom quarter, no phone frame/status bar/icons/address bar/UI.
- Asset visually inspected: clean portrait artwork, correct Sandium text and folded S, sparse stars and navy depth. Existing focal point (409,960), wallpaper provider/preferences and custom wallpaper paths are unchanged. No native UI has been baked into the background.
- Native shortcut bounds/order/labels/touch handlers unchanged. Raised style adds 4dp static elevation, restrained top-to-bottom charcoal gradient and edge highlight. No runtime blur or wallpaper sampling.
- Shortcut artwork normalization is display-only and never writes preferences, cached bitmap or user data. Only balanced transparent or near-uniform neutral perimeter padding is trimmed, with safety rim and capped zoom. Coloured, asymmetric, full-bleed or uncertain artwork retains its original.
- Original icon appears immediately; scanning/cropping runs on one low-priority worker, at most 25 queued jobs and 512×512 pixels per job. New rendering, hiding or detaching cancels work and invalidates completion; stale generation/removed views cannot receive results. Queue rejection and unreadable bitmap preserve the visible original.

## Validation

`test-sandium-shortcut-artwork.py` compiles/exercises the actual production Java normalization and worker methods with Android stand-ins. It covers transparent/white/black padding, full-bleed/coloured/corner-mark/asymmetric/empty/size fallbacks, immutable source pixels, no UI-thread pixel read, bounded queue, cancellation, hidden/detached/stale results and unreadable bitmap fallback. It does not establish Android rendering/frame-time performance.

`test-sandium-home-shortcuts.py` covers source composition, repeat application, geometry/order, custom-label persistence and native resource contracts. `test_shortcut_artwork.py` additionally checks asset hash/dimensions/focal point. Actual APK compilation and physical-device visual/touch/performance QA remain required before claiming runtime verification. No phone build was started for this patch.
