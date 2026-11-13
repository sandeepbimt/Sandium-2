set -euo pipefail
ROOT="$CIRCLE_WORKING_DIRECTORY"
SRC="$ROOT/brave-work/src"
CORE="$SRC/brave"
python3 .circleci/scripts/apply-sandium-ui-prune.py --core "$CORE" --src "$SRC"
python3 .circleci/scripts/test-sandium-ui-prune.py --core "$CORE" --src "$SRC" --repo-root "$ROOT"
# Final identity pass after all functional overlays; source identifiers and legal/service names stay intact.
python3 .circleci/scripts/apply-sandium-visible-branding.py --core "$CORE" --report "$ROOT/sandium-visible-branding-report.json"
python3 .circleci/scripts/test-sandium-visible-branding.py --core "$CORE"

# Final shared native palette after identity / functional resource overlays.
python3 .circleci/scripts/apply-sandium-native-theme.py "$CORE"
python3 .circleci/scripts/test-sandium-native-theme.py

# Bounded Android 16 portrait/top-toolbar web-underlap trial; no frost.
python3 .circleci/scripts/apply-sandium-scroll-status-bar.py "$SRC"
python3 .circleci/tests/test_status_underlap_patch.py

# Selected grouped site popup; keep underlying Shields policies and handlers.
python3 .circleci/scripts/apply-sandium-shields-popup.py "$CORE"
python3 .circleci/scripts/test-sandium-shields-popup.py --core "$CORE"
