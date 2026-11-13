set -euo pipefail
ROOT="$CIRCLE_WORKING_DIRECTORY"
SRC="$ROOT/brave-work/src"
CORE="$SRC/brave"
python3 .circleci/scripts/apply-sandium-homepage-adblock-warmup.py --core "$CORE" --src "$SRC"
python3 .circleci/scripts/apply-sandium-download-concurrency.py --src "$SRC"
python3 .circleci/scripts/apply-sandium-welcome-setup.py --core "$CORE" --src "$SRC" --repo-root "$ROOT"
python3 .circleci/scripts/test-sandium-homepage-adblock-warmup.py
python3 .circleci/scripts/test-sandium-download-concurrency.py
python3 .circleci/scripts/test-sandium-welcome-setup.py
python3 .circleci/scripts/test-sandium-page-transition-full.py
python3 - "$CORE/android/java/org/chromium/chrome/browser/settings/AppearancePreferences.java" <<'PY'
from pathlib import Path
import sys
source = Path(sys.argv[1]).read_text(encoding="utf-8")
required = (
    "PREF_SANDIUM_PAGE_TRANSITION_DARKEN = \"sandium_page_transition_darken\"",
    "findPreference(PREF_SANDIUM_PAGE_TRANSITION_DARKEN)",
    ".getBoolean(PREF_SANDIUM_PAGE_TRANSITION_DARKEN, false)",
    ".putBoolean(PREF_SANDIUM_PAGE_TRANSITION_DARKEN, (Boolean) newValue)",
)
missing = [item for item in required if item not in source]
if missing:
    raise SystemExit("SANDIUM_TRANSITION_JAVA_GATE=FAIL missing=" + repr(missing))
if source.count("PREF_SANDIUM_PAGE_TRANSITION_DARKEN =") != 1:
    raise SystemExit("SANDIUM_TRANSITION_JAVA_GATE=FAIL declaration count mismatch")
print("SANDIUM_TRANSITION_JAVA_GATE=PASS darken_constant=1 init=present change_handler=present")
PY
python3 .circleci/scripts/verify-sandium-vanilla-brave.py --core "$CORE" --src "$SRC" --out "$SRC/out/android_Release_arm64" --phase verify
