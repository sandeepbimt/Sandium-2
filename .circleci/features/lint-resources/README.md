# Exact #1394 resource lint repair

This inventory is for failed revision `68eb3032aed511ed5b49ac3a85464a16b9eb3d37`,
Brave 1.98.62 `44a84b1f89d9a35287289d6a3d493e362f5a5123` and Chromium
`d331de35ca8ab1358c7a17e4bd41627d55eaef51`. It is not the 1.99 upgrade inventory.

All 328 unique UnusedResources diagnostics are reviewed:
- 320 exact resource-message exceptions, with pinned definition/consumer/XML-chain
  or explicit live source/launcher evidence;
- 7 obsolete owned string declarations removed by the accompanying lint repair;
- 1 nonexistent upstream palette alias removed from the owned COMMON generator.

The last item is not an upstream color deletion. Exact Chromium d331's palette
contains surface, low, high and highest container colors, but no
`gm3_baseline_surface_container_lowest_dark`. Sandium's generator invented this
extra declaration, no owned consumer refers to it, and #1394 lint reported it
unused. All real upstream palette declarations and active overrides remain.
The canonical source reset restores brave_colors.xml before palette replay, so
an older checkpoint's generated extra alias does not survive preparation.

The helper runs at the end of product-overlay-30. It verifies the exact Brave
HEAD, pinned official hook and suppression-file bytes, unchanged removal recipe,
and hashes/absence checks for owned removals. It refuses unknown live lint rules
instead of overwriting them. Existing upstream lint entries are preserved; only
exact reviewed UnusedResources messages are added. No baseline, severity,
`--warnings-as-errors`, lint target, resource group or feature-removal policy is
disabled. Other and newly introduced diagnostics remain fatal.

Evidence is static: exact-pinned Java/XML chains, final source composition and
source-list/target dependency declarations. The retained same-pin composition
passed reset/replay/interruption/bad-patch checks. These do not claim an executed
GN graph, Android lint, successful build, APK or runtime result. Fresh service
validation remains required. The lint mechanism for live Settings/launcher false
positives is not established; their verified uses must not be deleted.

Local tests:
- `python3 -m unittest discover -s tests -p test_1394_lint_resources.py -v`
- `python3 .circleci/scripts/test-sandium-native-theme.py`
