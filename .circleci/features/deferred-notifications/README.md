# Deferred native notification permission (candidate)

Target Brave1.98.62 44a84b1f89d9a35287289d6a3d493e362f5a5123, Chromium156.0.8078.74 d331de35ca8ab1358c7a17e4bd41627d55eaef51. Exact upstream controller/coordinator fixtures are hash-recorded. Applies only two existing Java owners, no new GN target.

Welcome owns default-on toggle and atomic persistent intent in dedicated `sandium_notifications`: enabled/defaulttrue, setup_completed, request_pending, request_attempted. Completion must not continue if disk commit fails. This helper does not grant permission and enabled does not mean Android permission is granted.

Controller suppresses automatic startup requests and contextual requests before completed setup/while pending or while toggle disabled. Coordinator waits for a resumed, focused, interactable normal native NTP, browsing layout, attached/shown/nonzero homepage view and no modal. It registers Android frame-commit then posts back to UI and rechecks current tab and view before calling the native controller. Existing Android eligibility, prior requests/denial, API/demo exclusions, field-trial limits remain. Only this first eligible handshake converts initial rationale into direct native OS choice. It does not reset OS or Chromium denial history.

Pending survives a welcome-triggered restart. Before attempting any OS request it synchronously commits pending=false and attempted=true. Failure prevents this OS request. SharedPreferences may already update process memory before disk failure, so retry is not guaranteed. This deliberately guarantees at-most-once attempt, not exactly-once display: process death after the commit but before OS dispatch can lose that attempt. A suppressed native eligibility also does not produce a later surprise startup prompt. No first-launch notification is posted.

Frame commit demonstrates a rendered frame submitted to the swap chain, not physical screen presentation. Software-only rendering has no frame-commit guarantee and is conservatively excluded; normal hardware-accelerated Android UI is expected. Tests still required on real phone: welcome→restart→NTP; default toggle off; pause/resume; modal; denial/pregrant; API32; app relaunch; changed tab/view; reentrant draw; disk failure; process interruption.

Apply: `python3 .circleci/scripts/apply-sandium-deferred-notifications.py --src "$src"` after pinned source/Brave patches and welcome overlay. Add BOTH owners in full and UI-only reset lists; preserve any exact upstream Brave patches before this overlay. The integration recipe now owns both inputs and the exact coordinator Brave patch; normal Full stage30 applies and verifies this overlay after the other product owners.

Test: `python3 .circleci/features/deferred-notifications/test_deferred.py` (source/transaction tests). These are actual fixture-anchor/idempotence/order assertions, NOT a full Android Java/NullAway compile or behavioral instrumentation test. No full Android compilation performed. Verify integration using exact source compilation before claiming shipped functionality.

API evidence: exact pinned chrome/browser/tab/java/src/org/chromium/chrome/browser/tab/Tab.java exposes nullable View getView; ui/android/java/src/org/chromium/ui/modaldialog/ModalDialogManager.java exposes isShowing. No polling timers or fixed delay masquerades as homepage readiness. Observer detached in onDestroy; posted callbacks recheck destroyed state.

Read-only postcomposition verification: append `--verify-only`. Missing or duplicate owned blocks fail without rewriting unrelated changes. The 156 controller has a two-argument constructor; normal-profile gating is explicitly passed into the deferred method by the coordinator, rather than importing the 158 constructor/tracker implementation.
