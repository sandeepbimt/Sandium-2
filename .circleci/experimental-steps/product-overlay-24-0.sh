set -euo pipefail
python3 .circleci/scripts/apply-sandium-native-navigation.py "$CIRCLE_WORKING_DIRECTORY/brave-work/src" --mode off
ROOT="$CIRCLE_WORKING_DIRECTORY"
SRC="$ROOT/brave-work/src"
CORE="$SRC/brave"
bash "$ROOT/.circleci/scripts/apply-sandium-branding.sh"
