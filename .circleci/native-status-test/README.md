# Isolated API15 native status test

Base: local adee264, exact tested tree-equivalent remote guard d8b029.
Brave tag v1.98.62 / core44a84b1f89d9a35287289d6a3d493e362f5a5123.
Chromium d331de35ca8ab1358c7a17e4bd41627d55eaef51.

Mapped-host-ELF all-caller guard successor30401e8 (remote47332e53) is included.
Its standalone runtime probe identified host ELF62; actual Sandium APK launch
remains to be verified. Parent coordinates one combined test run, no duplicates.
No normal publication/reference renewal/shared cache saves are added.

Only experiment/native-status-api15 branch can run. run_build defaults false.
Normal restored-pin/integrity checks happen before cleanup or preparation.
The early cleanup exactly reverses any checkpoint native candidate before normal
product replay. After normal overlays/removal reset and JNI guard application,
prepare.py explicitly enables NTP+Settings and the separate reviewed secondary
owner candidate for Welcome/Bookmarks/History. Both flags are test-only. No independent browser-control geometry experiment is enabled.

Source preparation includes the exact-pinned internal theme dependency. Artifacts
are sandium-native-status-test-only, NOT normal phone release artifacts.

Before trigger: rerun source tests, canonical/Full isolation tests, regenerate
exact config/checksum after any guard merge, and refresh candidate manifest.
After APK: inspect Android15 cold/warm NTP/Settings first frame, wallpaper async,
light/night, dialogs/bottom sheets, IME, rotate, portrait cutout, status indicator,
Back transitions, and icon contrast. No claim of all-native-screen coverage.
