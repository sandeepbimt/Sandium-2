# Inactive popup-policy lifecycle experiment

Not imported by any build/apply script and not shipped. Run `python3 -m unittest -v` here.

This is an executable lifecycle/decision contract, **not working popup filter support**. No filter parser, Rust matcher or browser bindings are implemented. Test URLs are synthetic; login/payment controls prove only that this policy model preserves an unmatched request, not real website compatibility.

Native prerequisites:
- Extend pinned Rust parser/request masks for popup and popunder, including serialized cache compatibility, negation, combined options and exception semantics. Do not alias to document.
- Real engine result must supply the Match fields; no regular-expression replacement parser.
- Chromium must resolve inherited frame origins, capture opener frame/top provenance and invoke the engine asynchronously with lifetime-safe continuation.
- Classify true popunder behavior separately; background disposition alone is insufficient.
- Define new-tab UI behavior before shipping: a network throttle runs after tab creation and cannot promise no visible empty tab.
- Actual default/additional engine precedence must remain identical to existing engine aggregation; this contract's Match is already the aggregated result.

Reference behavior: https://github.com/gorhill/uBlock/blob/master/src/js/tab.js . This experiment is independently written, not copied from its GPL code.

Safety invariants exercised: native denial, Shields off, unmatched legitimate destinations, exceptions/important aggregate result, separate types, redirect provenance, stale/double completion cancellation, destruction and finished-opening lifetime. Browser/runtime tests remain required.
