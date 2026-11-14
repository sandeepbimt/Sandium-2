set -euo pipefail
ROOT="$CIRCLE_WORKING_DIRECTORY"
SRC="$ROOT/brave-work/src"
CORE="$SRC/brave"
# Disposable fixture-tree check; reads pinned blobs, never edits the build tree.
python3 .circleci/scripts/test-sandium-removal-composition.py --source "$CORE"
python3 .circleci/scripts/sandium-removal-recipe.py --core "$CORE" --src "$SRC" --out "$SRC/out/android_Release_arm64" --phase apply
python3 .circleci/scripts/audit-sandium-removal-graph.py --src "$SRC" --out "$SRC/out/android_Release_arm64" --report "$ROOT/brave-apk/removal-native.json"
python3 .circleci/scripts/audit-sandium-low-coupling.py --src "$SRC" --out "$SRC/out/android_Release_arm64" --report "$ROOT/brave-apk/removal-low-six.json"
python3 .circleci/scripts/audit-sandium-leo-removal.py --core "$CORE" --deps-file "$ROOT/brave-apk/removal-native.deps.txt" --report "$ROOT/brave-apk/removal-leo.json"
