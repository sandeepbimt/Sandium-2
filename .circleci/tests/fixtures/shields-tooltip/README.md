# Shields educational tooltip fixtures

Source: Brave core `44a84b1f89d9a35287289d6a3d493e362f5a5123`.
The three XML files are upstream resources (trailing whitespace normalized) under
`android/java/brave-res/{drawable,layout}`. The Java fixture is the
`showTooltip` method excerpt from `BraveToolbarLayoutImpl.java`; the full pinned
file is exercised by `test-sandium-removal-composition.py`.

The style transform is limited to colors and corner radii. It preserves the
semantic success icon, tooltip anchoring, text/counters, click/dismiss handling,
and once-only education preference. It does not theme web content.
