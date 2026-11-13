set -euo pipefail
CORE="$CIRCLE_WORKING_DIRECTORY/brave-work/src/brave"
# Reset shared native files BEFORE every consumer overlay.
python3 .circleci/scripts/apply-sandium-adblock-engine-race.py --reset-shared "$CORE"
python3 .circleci/scripts/apply-sandium-filter-subscriptions.py --core "$CORE"
python3 .circleci/scripts/apply-sandium-filter-bootstrap.py --core "$CORE"
