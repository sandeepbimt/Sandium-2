# Search choices follow-up to #1171

Pinned Brave 44a84b1f89d9a35287289d6a3d493e362f5a5123, Chromium d331de35ca8ab1358c7a17e4bd41627d55eaef51.

- Disable QuickSearchEnginesUtil's feature gate, so the engine shortcut strip cannot appear above the keyboard even with an old enabled preference. Native typed suggestions and autocomplete remain intact.
- Filter Brave Search by prepopulated identity and pinned keyword `:br` (and legacy `search.brave.com`) from both Chromium legacy and V2 provider lists. Do not filter arbitrary display names.
- Both normal and private screens use the same adapter. Where Brave is the saved active provider, activation narrowly changes it to the existing prepopulated Google template (ID 1, `:g` or `google.com`) and updates that profile's saved short name. Other providers are untouched. No OTR profile is instantiated for migration.
- Search-provider policy wins. An enterprise-managed default is not migrated; The prior ui-prune overlay still hides it from choices; the active managed default itself stays unchanged. If Google is missing, retain the old default rather than invent a URL or leave search unusable. These are explicit exception paths, not claims of unconditional removal.
- Run migration before Settings snapshots current engine, and when its service finishes loading, because upstream re-adds a missing active default.
- No search index, browsing data, or custom engine storage is deleted. Existing quick-strip preference remains stored but ineffective.

Validation: six pinned-source/idempotence/guard tests; Full pipeline wiring passes; diff checks pass. Android compile, device normal/private provider selection and typing testing remain required. Source tests are not runtime proof.

A Java behavioral harness extracts the exact transformed `updateActiveDSE` method and covers ten profile/policy/custom-engine cases. It has NOT run here because this executor has no `javac`; it is intentionally not an unconditional CI overlay step. Run it in a JDK environment before considering behavioral coverage passed.
