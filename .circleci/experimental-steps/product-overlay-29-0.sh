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

# Bounded Android 16 portrait top/bottom-toolbar web-underlap trial; no frost.
python3 .circleci/scripts/apply-sandium-scroll-status-bar.py "$SRC"
python3 .circleci/tests/test_status_underlap_patch.py

# Selected grouped site popup; keep underlying Shields policies and handlers.
python3 .circleci/scripts/apply-sandium-shields-popup.py "$CORE"
python3 .circleci/scripts/test-sandium-shields-popup.py --core "$CORE"

# Native bottom toolbar and paged menu preserve existing omnibox and action dispatch.
python3 .circleci/scripts/apply-sandium-bottom-toolbar.py --src "$SRC" --core "$CORE"
python3 .circleci/scripts/test-sandium-bottom-toolbar.py --src "$SRC" --core "$CORE"
python3 .circleci/scripts/apply-sandium-paged-menu.py "$SRC" --repo "$ROOT"
python3 .circleci/scripts/apply-sandium-paged-menu.py "$SRC" --repo "$ROOT" --verify-only

python3 .circleci/scripts/apply-sandium-chrome-theme.py "$SRC"
python3 .circleci/scripts/test-sandium-chrome-theme.py
python3 .circleci/scripts/test-sandium-motion.py

# Frozen unified bar follows the intermediate bottom-toolbar source contract.
python3 .circleci/scripts/apply-sandium-unified-address.py --src "$SRC" --core "$CORE"
python3 .circleci/scripts/apply-sandium-unified-address.py --src "$SRC" --core "$CORE" --verify-only
python3 .circleci/scripts/test-sandium-unified-address.py

# Device-feedback corrections preserve native security and native URL text ownership.
python3 .circleci/scripts/apply-sandium-toolbar-refinements.py --src "$SRC"
python3 .circleci/scripts/apply-sandium-toolbar-refinements.py --src "$SRC" --verify-only
python3 .circleci/scripts/test-sandium-toolbar-refinements.py
# No typing engine strip; Brave omitted from both Android engine-choice screens.
python3 .circleci/scripts/apply-sandium-search-choices.py --core "$CORE"
python3 .circleci/scripts/apply-sandium-search-choices.py --core "$CORE" --verify-only
python3 .circleci/scripts/test-sandium-search-choices.py

# Refresh same-position native focus geometry; device placement still needs testing.
python3 .circleci/scripts/apply-sandium-focus-follow.py --src "$SRC"
python3 .circleci/scripts/apply-sandium-focus-follow.py --src "$SRC" --verify-only
python3 .circleci/scripts/test-sandium-focus-follow.py
