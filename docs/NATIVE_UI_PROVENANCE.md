# Native UI candidate provenance and distribution review

This candidate integrates only the menu and native toolbar modules. It does not import Brave, Soul2, uBlock, or another browser's implementation or assets.

- Native menu/toolbar fixtures are pinned Chromium source, with their upstream headers and LICENSE copies retained in each experiments directory. Fixture digests are checked by the source planners.
- New RawS menu implementation and transformation scripts are newly authored in this repository. Native menu action dispatch, icons, strings and permission ownership remain Chromium paths; they are not relabelled as independently owned RawS assets.
- Toolbar changes are paint-only transformations of pinned Chromium files; original upstream notices remain.
- No additional downloaded font, image pack, paid asset, filter list or browser engine is introduced by these two modules.

This is provenance evidence, not legal clearance of the entire Chromium distribution. Chromium contains separately licensed third-party components. Preserve the upstream credits/notices and review the exact packaged dependency inventory before distribution or monetization. Do not assume all dependencies share the top-level BSD-style licence or that every later RawS addition permits private-source distribution. Review new/copied dependencies and their linkage/distribution terms individually.
