set -euo pipefail
ROOT="$CIRCLE_WORKING_DIRECTORY"
SRC="$ROOT/brave-work/src"
CORE="$SRC/brave"
python3 .circleci/scripts/apply-sandium-ui-prune.py --core "$CORE" --src "$SRC"
python3 .circleci/scripts/test-sandium-ui-prune.py --core "$CORE" --src "$SRC" --repo-root "$ROOT"
# Final identity pass after all functional overlays; source identifiers and legal/service names stay intact.
python3 .circleci/scripts/apply-sandium-visible-branding.py --core "$CORE" --report "$ROOT/sandium-visible-branding-report.json"
python3 .circleci/scripts/test-sandium-visible-branding.py --core "$CORE"
