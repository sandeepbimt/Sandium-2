set -euo pipefail
ROOT="$CIRCLE_WORKING_DIRECTORY"
SRC="$ROOT/brave-work/src"
CORE="$SRC/brave"
# Disposable fixture-tree check; reads pinned blobs, never edits the build tree.
python3 .circleci/scripts/test-sandium-removal-composition.py --source "$CORE" --gn "$SRC/buildtools/linux64/gn"
python3 .circleci/scripts/sandium-removal-recipe.py --core "$CORE" --src "$SRC" --out "$SRC/out/android_Release_arm64" --phase apply
# Run every independent audit before failing, so one build reports all graph defects.
python3 .circleci/scripts/precheck-graph.py --audits-only
