set -euo pipefail
ROOT="$CIRCLE_WORKING_DIRECTORY"
SRC="$ROOT/brave-work/src"
CORE="$SRC/brave"
# Disposable fixture-tree check; reads pinned blobs, never edits the build tree.
python3 .circleci/scripts/test-sandium-removal-composition.py --source "$CORE" --chromium-source "$SRC" --gn "$SRC/buildtools/linux64/gn"
# Post-UI diagnostics; preserve the frozen UI overlay wrapper byte-for-byte.
python3 .circleci/scripts/trace-sandium-back-geometry.py "$SRC"
python3 .circleci/scripts/sandium-removal-recipe.py --core "$CORE" --src "$SRC" --out "$SRC/out/android_Release" --phase apply
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

# Run every independent audit before failing, so one build reports all graph defects.
python3 .circleci/x64-test/precheck-graph.py --audits-only
python3 .circleci/scripts/removal-evidence.py capture --root "$ROOT"
