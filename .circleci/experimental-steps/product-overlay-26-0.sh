set -euo pipefail
python3 .circleci/scripts/apply-sandium-page-transition-full.py "$CIRCLE_WORKING_DIRECTORY/brave-work/src"
python3 .circleci/scripts/apply-sandium-back-transition.py "$CIRCLE_WORKING_DIRECTORY/brave-work/src"
