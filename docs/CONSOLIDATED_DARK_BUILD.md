# Consolidated Dark Pages candidate after #1177

Includes the hermetic status test repair, reviewed tooltip/welcome, menu cross-page movement and saved ordering, atomic homepage prepend, bounded press feedback and removal of cosmetic welcome restart delay. Existing selected UI changes and thirteen-component removal remain composed.

Dark Pages and manual correction now run as one pinned staged overlay after the existing UI, removal, home and fullscreen-only video consumers. Both native repository pins are checked. All affected inputs are registered for full and UI reset; four existing Brave patches on Chromium inputs are replayed. Generated outputs are included in reset cleanup. A second staging replay validates the entire result before writes, followed by production readback. This is not filesystem-transactional against process termination or storage failure during writes; canonical reset/replay provides recovery.

Local evidence: 266 host suite tests passed with one Java dispatch test skipped because javac is unavailable; two expanded Dark composition tests passed; full pinned UI/removal/Dark reset, replay, interrupted recovery and bad-patch preflight passed. Native owner review and final integrated review are separate gates. None of these checks establishes Android/Blink compilation or device behavior. JNI/Mojo/resource compilation, APK inspection and device navigation/settings/manual-corrector testing remain required.

Loading indicator work is diagnostic, not a demonstrated visual fix. Brave external-link suppression remains scoped, not an exhaustive compiled UI audit. Existing status gradient and general fluidity require device verification.
