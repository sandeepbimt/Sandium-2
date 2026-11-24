# RawS scriptlet coverage: verified source census, not runtime parity

The catalog has 30 network rows; it does not contain 30 packaged filter
bodies. At this checkout, the only packaged list body is the pinned EasyList.
The only separately verified archived catalog response available here is an
older immutable uAssets Ads root for slot 0. That archive is not proof of the
bytes cached on any phone, or of a currently served response. **29 other
catalog bodies were not measured**, including the remotely served EasyList
row. Do not extrapolate past the corpus below.

The census verifies SHA256 against the exact product recipe or fixed archive
and verifies Git blob identity for the two historical uAssets inputs. It uses
the exact browser condition-pruning and typed policy sources from the recipe,
compiled with a narrow host stand-in for safe span. Numeric results below
are text-line counts (including duplicate rules), not native Rust matcher
acceptance, matched pages, warning removal, or Android effect measurements.

| Verified local body | uBO-shaped positives after preprocessing | Positive families | uBO-shaped exceptions | Exact slot-0 projection |
|---|---:|---:|---:|---:|
| Packaged EasyList | 0 | 0 | 0 | Ineligible |
| Historical uAssets Ads root at `a21816ca…` | 2,421 (2,425 before pruning) | 39 | 3 | 2 |
| Historical root with offline children expanded | 9,545 (9,559 before pruning) | 82 | 31 | Not installed; counterfactual only |

The expanded variant also carries one AdGuard-shaped positive after pruning.
The current product does not recursively fetch those children. Neither the
expanded uAssets feed nor any new rule was added in this change.

## What is actionable

- **Phase coverage:** By default, the reviewed lane executes no scriptlets.
  When explicitly enabled, both reviewed operations are one-shot DOM
  mutations after `DOMContentLoaded`, at most once per eligible document;
  no document-start, early inline interception, iframe, or late mutation
  observation is supported. Host lifecycle tests cover retry admission
  within the original 300 ms window, not earlier execution.
- **Closest adjacent action:** The archived Ads root has 28 `ra`
  (`remove-attr`) positives. The only two custom metadata removals are
  the two already reviewed. The rest change link/frame behavior (15),
  event handler attributes (9), or other functional DOM semantics (2).
  The current review authorizes none of those, and they are not safe
  generalizations of a metadata-only mutation. The 7 metadata-shaped
  positives in the expanded counterfactual do not establish loaded
  source provenance. Do not infer permissions from the number of rules.
- **Largest gaps are not additional DOM metadata removals:** The archived
  root includes 633 property-read abort, 342 current-script interception,
  and 296 constant-setting positives. These classes can interfere with
  page JS execution before or during parsing and are outside the reviewed
  isolated DOM boundary. At this time their frequency supplies no approval
  for main-world interception, arbitrary arguments, or storage/cookie access.
- **Next safe timing candidate:** Precompute the same typed permit after final
  response in the browser, without dispatching any code before the current
  committed visible-document gate. A precomputed permit needs the final URL,
  navigation and matcher identities, exact current document lease/token,
  current prefs and JS policy, and all existing vetoes; consume at most once
  at DOMContentLoaded. Require native race tests for redirects, simultaneous
  navigation, worker refresh and exceptions between query and commit,
  prerender/BFCache, disabled Shields, obsolete URL and policy changes. This
  could save time spent waiting for worker admission; it would **not**
  achieve document-start support. There is no native environment here to
  establish that first proof, so the measurement commit adds no execution
  behavior. A renderer-timing seam is not sufficient by itself to authorize
  running before the browser's exact-document checks.

## Repeat locally

From the product checkout, with the separately verified locally archived
uAssets root, run:

```sh
python3 -B raws-adblock/audit/scriptlet_census.py   --ads-root /path/to/archived-uassets/filters/filters.txt   --illustrative-expanded /path/to/expanded-offline-uassets-ads.txt
```

The expanded input is optional; both supplied files are rejected unless they
match the sealed identities. Output contains counts/hashes and action names,
not publisher scopes or rule arguments. The archived census beside this
note was regenerated twice with byte-identical output.
