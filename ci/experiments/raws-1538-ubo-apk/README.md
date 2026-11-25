# RawS Android: full uBlock Origin MV2 admission candidate

Source only. Pinned Chromium revision: 52bdd21723d5db0c9ab11716d38feac74828cf84.
Target: corrected #1538 plus the isolated Afterbird Desktop Android extension
preflight. Keep the official branch, test signing, native Lens and ordinary
download safeguards unchanged. No extension is installed at startup.

- An exact, user-initiated publisher release download opens through the
  existing CRX installer, never in a private profile. It requires prompt UI.
- The expected ID and exact version go through normal installer checks.
  The normal sandboxed signature verifier checks the exact original package
  digest on its private copy before extraction. A directory with a copied
  publisher public key does not qualify.
- Only the exact installed internal MV2 identity, version and public key get
  a startup/enable exception. Standard blocklist, requirements, permissions
  and other management checks remain separate. Do not use an unpacked CRX.
- This does not assert that Android's Downloads UI reaches the same callback
  on a phone, or that full uBO's blocking API works on this Chromium build.

Verification completed: patch apply/reverse against exact preimages; C++20
identity positive and negative assertions; publisher signature and archive
digest verification. No GN generation, full native build or Android runtime.

Acceptance on an isolated Android test profile: attempt the exact publisher
release download; ensure normal download handling and explicit permissions
prompt. Cancel once, then accept. Confirm that a modified CRX, unrelated MV2
and unpacked lookalike do not install through this route. Verify the extension
opens, blocks one known network request, allows a control request, and hides a
known element, with Sandium disabled only in the disposable validation lane.
Force-stop, restart, and verify enable/disable and policy persistence. The Lens
link and production engine handoff are deliberately not part of this patch.
