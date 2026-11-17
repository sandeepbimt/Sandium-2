set -euo pipefail
python3 .circleci/scripts/apply-sandium-native-navigation.py "$CIRCLE_WORKING_DIRECTORY/brave-work/src" --mode off
python3 .circleci/scripts/apply-sandium-navigation-diagnostics.py "$CIRCLE_WORKING_DIRECTORY/brave-work/src" --reset-native-probes
python3 .circleci/scripts/apply-sandium-page-transition-full.py "$CIRCLE_WORKING_DIRECTORY/brave-work/src"
python3 .circleci/scripts/apply-sandium-back-transition.py "$CIRCLE_WORKING_DIRECTORY/brave-work/src"
python3 .circleci/scripts/apply-sandium-back-controls.py "$CIRCLE_WORKING_DIRECTORY/brave-work/src"
python3 .circleci/scripts/trace-sandium-back-geometry.py "$CIRCLE_WORKING_DIRECTORY/brave-work/src" --reset
