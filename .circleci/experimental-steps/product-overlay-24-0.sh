set -euo pipefail
ROOT="$CIRCLE_WORKING_DIRECTORY"
SRC="$ROOT/brave-work/src"
CORE="$SRC/brave"
bash "$ROOT/.circleci/scripts/apply-sandium-branding.sh"
