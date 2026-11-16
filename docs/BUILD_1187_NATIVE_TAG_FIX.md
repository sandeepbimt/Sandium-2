# Build 1187 native HTML-tag correction

Build 1187 passed UI pruning and the thirteen-group source/build-graph audits.
The native compiler then rejected three references in `sandium_element_colors.cc`:
two `kIframeTag` references and one `kHtmlTag` reference. Chromium's exact pinned
name generator preserves the acronyms as `kIFrameTag` and `kHTMLTag`.

This correction changes only those names, retaining every eligibility exclusion,
iframe/control safeguard and document/lifecycle guard. All 19 neighboring HTML
tag constants were checked against the pinned generator. A source regression
checks the complete set, including the two acronym spellings.

Validation: 266 repository tests passed (one pre-existing missing-javac skip),
two combined Dark Pages/manual-corrector composition tests passed, and six
native source guards passed. These are not a substitute for full Android native
compilation or device behavior tests. Build 1187's incremental payload and receipt
were saved before its honest-completion gate rejected the deterministic failure.
