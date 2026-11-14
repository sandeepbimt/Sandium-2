# Combined UI/removal build #1152: shared Java consumer closure

Actual CI evidence (2026-11-14): chrome_java compile failed with 17 errors:
- 12 Settings search registry references to excluded Playlist, Leo, Origin, Wallet/Web3 and VPN providers.
- Rewards observer `onTermsOfServiceUpdateAccepted` retained `@Override` after its observer interface was removed.
- Four reads/writes of removed `BravePref.SPONSORED_ENABLED` in shared Privacy and Background Images settings.

The run saved its incremental payload and published its checkpoint receipt before its final gate deliberately rejected a deterministic failure. No fresh validated APK was produced.

Correction: apply scoped Java closure after removal overlays. Remove only obsolete registry providers (keep ordinary Settings search), remove the obsolete observer callback, and remove sponsor preference access/listeners and UI entries through each preference's actual parent. Keep ordinary wallpapers, Shields and #1150 UI/gold/startup fixes. Do not restore removed implementation or bypass any Origin entitlement/payment gate.

Reset/replay now includes the pinned Chromium registry and exact pinned Brave patch. A pinned fixture is included for source composition. Future upgrades must revalidate these source anchors rather than silently skip missing entries. Verify full UI/removal composition, interrupted replay, and source checks; actual Android compilation and phone testing remain separate requirements.

Validation for this candidate: 203 repository unit tests passed; pinned UI + complete removal composition, reset/replay and interrupted-recovery tests passed; independent source review passed. Android compile and runtime are not implied by these checks.
