# Ordinary iframe typography snapshot candidate

Dormant module: apply `renderer/oopif.py` after `renderer/apply.py`, itself after dark-pages renderer patches. No CI activation or build is included.

## Policy lifetime

* A fresh main-document navigation calculates the final-URL policy once. The outgoing clone value is retained in the browser-owned NavigationRequest.
* Only an accepted, waiting-to-commit new main document captures that value into its new PageImpl, after document-associated data resets. Same-document navigation and BFCache/prerender activation skip this capture.
* Ordinary iframe navigation copies its parent's PageImpl snapshot, not current preferences. This applies even if the user saved a different value since the main document loaded.
* Only regular Blink local-root commits set renderer-local Page settings. Local children inherit rather than mutate shared settings. Every ordinary OOPIF in the same owning Page therefore receives the same snapshot; failed child navigations also receive that snapshot instead of resetting sibling settings.
* The user stylesheet is installed before initial viewport style for each HTTP(S) document and parent-guarded about:blank/srcdoc document. Ordinary local initial empty children share the existing parent Page settings; regular OOPIF about/srcdoc commits use the captured snapshot. A newly initialized local root under a remote parent may still have default policy before its regular commit; this candidate does not promise coverage of that initial-empty edge or install a late update. Top-level about and arbitrary about pages are excluded.
* Inner main documents such as fenced frames/guest pages are separate Pages, not ordinary OOPIFs; their policy is own/default, not an asserted extension of the embedder's captured global policy.

## Exact-source evidence

Chromium d331de35ca8ab1358c7a17e4bd41627d55eaef51: PageImpl documents per-cross-document lifetime; RenderFrameHostImpl::GetPage returns the main document's owned Page. DidCommitNavigationInternal creates/reset document-associated data before the new capture. DocumentLoader::CommitNavigation invokes DidCommitNavigation after DidInstallNewDocument and before opening document content. These are source-level ordering observations, not measured IPC runtime proof.

## Validation and remaining gate

Ten tests check exact RFHI fixture SHA256, composition/idempotence, mismatch atomicity, new-document guards, snapshot-only child transport, pre-document local-root setter placement, failed-child behavior, and compiled extracted normalizer plus snapshot model. The model does not execute Chromium, navigation IPC, BFCache, or prerender. Full Chromium compile and runtime ordinary OOPIF/sibling/error-navigation/BFCache/prerender tests remain mandatory. Default 100/Off must compare identically with baseline. This patch does not claim first-paint/performance or no-reflow runtime validation.
