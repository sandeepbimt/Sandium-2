# Next-run #1171 corrections

Based on published a4cd546 (#1171), retaining its navigation code unchanged.

Includes reviewed UrlBar native layout ownership crash fix 3dfd828; toolbar/menu f6b87d2; search series through 41d3c1e; bounded same-position focus refresh 86e0809; expiry-aware optional refresh through c864f26.

Stage29 applies unified address, toolbar refinements, search choices, then native focus refresh, each with readback and contracts. Search needs three Brave source resets and the Chromium SearchEngineAdapter reset plus its pinned Brave patch. These are explicitly registered and exercised in full reset/replay and interrupted-removal recovery. No relaxed source anchors or removal gates.

Optional refresh uses the earliest inherited base/increment deadline with an inclusive two-day margin. Deadlines are conservative receipt capture+14 days, not queried service expiration; unknown/malformed metadata fails closed. Existing APK-first and capacity-triggered scheduled compaction remain. The proposed navigation daily schedule is NOT saved yet, awaiting owner approval. No immediate maintenance run.

Validation: full pinned composition/replay/interruption passes. Source tests are not Android compile or device proof. Search tests preserve managed defaults, custom engine collisions and missing-Google fallback; Java migration runner requires a Java compiler unavailable here. Focus refresh is not proof the bar follows the keyboard correctly. Blue-flash behavior deliberately unchanged. Native device tests still needed for launch, tab short/long press, menu edits and submenu back, normal/private search defaults, keyboard placement, rotation and accessibility.

## Final address presentation clarification

The centered, bounded URL has no added inner pill/background. Existing implementation already uses one enclosing native surface, and adds no UrlBar background drawable. Added a contract protecting this requirement rather than changing native painting unnecessarily. Ordinary display uses Chromium's formatter to omit scheme, path and trivial `www`, so `https://www.abc.com/path` displays `abc.com`; meaningful subdomains and ports remain for identity safety. Full native URL editing is unchanged. This source contract does not establish screenshot-perfect rendering.
