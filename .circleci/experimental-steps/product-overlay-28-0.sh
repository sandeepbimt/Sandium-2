set -euo pipefail
CORE="$CIRCLE_WORKING_DIRECTORY/brave-work/src/brave"
python3 .circleci/scripts/apply-sandium-shields-two-state.py "$CORE"
python3 .circleci/scripts/apply-sandium-adblock-engine-race.py "$CORE"
python3 .circleci/scripts/test-sandium-shields-two-state.py
python3 .circleci/scripts/test-sandium-adblock-engine-race.py
python3 .circleci/scripts/test-sandium-filter-subscriptions.py
python3 .circleci/scripts/test-sandium-filter-bootstrap.py
