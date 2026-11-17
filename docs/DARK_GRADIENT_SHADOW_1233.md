# Dark-page paint consistency candidate (#1233)

The reported screenshot shows a white gradient patch in a search field and bright parallel separator strokes. These symptoms are consistent with two independently confirmed source-level gaps. We have not inspected the original page DOM or reproduced this screenshot on the patched Android build, so the exact page-level attribution remains unverified.

## Confirmed code gaps

1. Managed ON globally disables `ImageAutoDarkMode`. CSS background gradients use this image path too. Pinned Chromium `GraphicsContext` forwards its `enabled` value into `ImageDrawOptions.apply_dark_mode`; `Gradient::ApplyToFlags` uses that value to transform CSS color stops through native background conversion. Therefore preserving photo pixels also accidentally preserved white gradient stops while solid backgrounds darkened.
2. `BoxPainterBase` shadow conversion checked only `style.ForceDark()`. Sandium uses a separate `SandiumPaletteEnabled` bit after clearing `ColorSchemeForced`. Shadow colors could remain light while the surrounding backgrounds darkened. CSS shadows are often used for separator strokes.

## Narrow fix

- Identify only `GradientGeneratedImage`, not all generated images, SVG, bitmap or paint worklets.
- Use native color-stop transformation in all three CSS background draw paths (single tile, repeated tile and rounded background). Select `kPhoto` intentionally to bypass image pixel classification/decoding; gradient-stop processing is independently driven by `apply_dark_mode`.
- Use the existing shared paint eligibility helper for shadow conversion, including the manual-color override gate.
- Preserve unmanaged native behavior, explicit OFF, manual corrections, page structure, authored CSS colors, form controls, photos and logos. No hostname rules, DOM injection, layout changes, or blanket border removal.

## Validation

- Exact pinned fixtures and hashes, repeat application and mismatch rejection.
- Compiled extracted helper matrix: managed ON/OFF/unmanaged, manual, stock dark, gradient versus protected image.
- Combined dark/manual composition replay and restoration inventory.
- `tests/fixtures/dark-pages-visual/gradient-shadow.html` is a visual check page, not a claim of Android screenshot validation.

Required Android validation before claiming resolution: original Google query with fresh rules and retained rules, native dark site, light site, rounded/repeated gradient controls, photos/SVG/bitmap logos; Dark Pages ON/OFF; saved corrections; reload and back/forward. Confirm pixels and geometry on the actual resulting APK.

Pinned upstream references: Chromium commit `d331de35ca8ab1358c7a17e4bd41627d55eaef51`, `third_party/blink/renderer/platform/graphics/graphics_context.cc` (DrawImage/DrawImageTiled/ImageDrawOptions), `gradient.cc` (ApplyToFlags/BuildShader), and `core/paint/box_painter_base.cc` (shadow resolution and three background-image paths). Read directly from the upstream repository at the pin, not assumed from current Chromium.
