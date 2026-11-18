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

## #1401 supplemental catalogue audit

Stage 2/job 4291 exposed 644 **new** unused-resource IDs, with zero overlap with
#1394's 320 exceptions. The original exceptions therefore worked. The new batch
is 630 strings, 3 plurals and 11 generated Nala drawables. Definitions and generator
mappings were checked at the exact 1.98.62 Git pin, not a newer upstream tree.

`inventory-1401.json` records the exact diagnostics, original Android Java/XML
references (verified Git blobs), composition status, and source provenance:
- 547 have pinned Java/XML chains through removed/replaced consumers;
- 86 are retained upstream UI catalogue entries, with original and composed
  reference evidence. Some composition files were not materialized; that is
  recorded explicitly, never treated as proof of exclusion;
- 5 still have shared composed references, so deleting them would be unsafe;
- 6 have no references in the audited Android Java/XML files. Four are Wallet
  catalogue entries; two are Chromium overlay entries (`fre_activity_label`,
  `search_widget_description`). This is not a claim of no native/manifest use.

The correction deliberately retains upstream declarations rather than expanding
feature stripping into shared GRIT/Nala catalogues. It extends Brave's existing
UnusedResources hook using **644 exact escaped message IDs**, not prefixes or
paths. This is an explicit retained-resource policy, not a claim that all 644 are
false positives or that every diagnostic was caused by Sandium. Other lint
issues, new resource IDs, severity, official flags, and warnings-as-errors remain
unchanged. All original upstream rules and original 320 rules are preserved.

The runtime helper verifies exact pinned catalogue/generator bytes and each
resource's definition before application. The accepted live suppression inputs
are only: original upstream, previous reviewed 320-rule result, or new exact
964-rule result. Any foreign live rule fails closed. This supports restoring the
#1401 stage-1 checkpoint without overwriting unknown lint state.

Validation: original six tests plus four supplement tests, including previous
320-rule migration, idempotency, tampered definitions, and foreign-rule rejection.
These are host checks, not a full lint execution, APK build, or runtime proof.
