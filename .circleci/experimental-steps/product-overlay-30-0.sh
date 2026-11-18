set -euo pipefail
python3 .circleci/scripts/apply-sandium-native-navigation.py "$CIRCLE_WORKING_DIRECTORY/brave-work/src" --mode off
python3 .circleci/scripts/apply-sandium-navigation-diagnostics.py "$CIRCLE_WORKING_DIRECTORY/brave-work/src" --reset-native-probes
ROOT="$CIRCLE_WORKING_DIRECTORY"
SRC="$ROOT/brave-work/src"
CORE="$SRC/brave"
# Disposable fixture-tree check; reads pinned blobs, never edits the build tree.
python3 .circleci/scripts/test-sandium-removal-composition.py --source "$CORE" --chromium-source "$SRC" --gn "$SRC/buildtools/linux64/gn"
# Migrate a resumed legacy UI checkpoint before applying later overlays.
python3 .circleci/scripts/apply-sandium-native-insets.py "$SRC"
python3 .circleci/scripts/sandium-removal-recipe.py --core "$CORE" --src "$SRC" --out "$SRC/out/android_Release_arm64" --phase apply
# Apply home UI after strict News-removal source transformations.
# Native five-column expandable home shortcuts, separate from launcher shortcuts.
python3 .circleci/scripts/apply-sandium-home-shortcuts.py "$SRC" --repo "$ROOT"
python3 .circleci/scripts/apply-sandium-home-shortcuts.py "$SRC" --repo "$ROOT" --verify-only

# Optional partial video stage: gestures only after normal site fullscreen entry.
python3 .circleci/scripts/apply-sandium-video-gestures.py "$SRC" --repo "$ROOT"
python3 .circleci/scripts/apply-sandium-video-gestures.py "$SRC" --repo "$ROOT" --verify-only

# Pinned Dark Pages and manual correction, staged together after all UI consumers.
python3 .circleci/scripts/apply-sandium-dark-combined.py "$SRC" --repo "$ROOT"
python3 .circleci/scripts/apply-sandium-dark-combined.py "$SRC" --repo "$ROOT" --verify-only
python3 .circleci/scripts/test-sandium-dark-composition.py

# Global webpage text: compose only after complete dark-policy verification.
python3 .circleci/features/page-text/apply.py "$SRC" --repo "$ROOT"
python3 .circleci/features/page-text/apply.py "$SRC" --repo "$ROOT" --verify-only
python3 .circleci/features/page-text/tests/test_combined.py

# Native homepage only: backing and matching paint after all prior UI owners.
python3 .circleci/scripts/apply-sandium-homepage-combined.py "$SRC"
python3 .circleci/scripts/apply-sandium-homepage-combined.py "$SRC" --verify-only
python3 .circleci/scripts/apply-sandium-capture-coherence.py "$SRC"
python3 .circleci/scripts/apply-sandium-capture-coherence.py "$SRC" --verify-only
# Native load state, full capsule-height green paint. No layout/viewport changes.
python3 .circleci/scripts/apply-sandium-address-progress.py "$SRC"
python3 .circleci/scripts/apply-sandium-address-progress.py "$SRC" --verify-only
python3 .circleci/scripts/test-sandium-address-progress.py
python3 .circleci/scripts/apply-sandium-native-insets.py "$SRC" --verify-only
python3 .circleci/features/page-text/apply.py "$SRC" --repo "$ROOT" --verify-only
# Bounded opt-in typed diagnostics after all product consumers.
python3 .circleci/scripts/apply-sandium-navigation-diagnostics.py "$SRC"
python3 .circleci/scripts/apply-sandium-navigation-diagnostics.py "$SRC" --verify-only
python3 .circleci/scripts/apply-sandium-native-navigation.py "$SRC" --mode configured
python3 .circleci/scripts/apply-sandium-native-navigation.py "$SRC" --mode configured --verify-only

# Run every independent audit before failing, so one build reports all graph defects.
python3 .circleci/scripts/precheck-graph.py --audits-only
python3 .circleci/scripts/removal-evidence.py capture --root "$ROOT"

# Exact same-pin #1394 resource review; preserve lint and upstream rules.
python3 .circleci/scripts/apply-sandium-lint-resources.py --core "$CORE"
