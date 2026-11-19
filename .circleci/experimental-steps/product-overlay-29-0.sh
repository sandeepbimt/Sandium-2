set -euo pipefail
python3 .circleci/scripts/apply-sandium-native-navigation.py "$CIRCLE_WORKING_DIRECTORY/brave-work/src" --mode off
python3 .circleci/scripts/apply-sandium-navigation-diagnostics.py "$CIRCLE_WORKING_DIRECTORY/brave-work/src" --reset-native-probes
ROOT="$CIRCLE_WORKING_DIRECTORY"
SRC="$ROOT/brave-work/src"
CORE="$SRC/brave"
python3 .circleci/scripts/apply-sandium-ui-prune.py --core "$CORE" --src "$SRC"
python3 .circleci/scripts/test-sandium-ui-prune.py --core "$CORE" --src "$SRC" --repo-root "$ROOT"
# Remove the startup promotion, including fragments restored from earlier APKs.
python3 .circleci/scripts/apply-sandium-no-video-promo.py --core "$CORE"
# Final identity pass after all functional overlays; source identifiers and legal/service names stay intact.
python3 .circleci/scripts/apply-sandium-visible-branding.py --core "$CORE" --report "$ROOT/sandium-visible-branding-report.json"
python3 .circleci/scripts/test-sandium-visible-branding.py --core "$CORE"

# Final shared native palette after identity / functional resource overlays.
python3 .circleci/scripts/apply-sandium-native-theme.py "$CORE"
python3 .circleci/scripts/test-sandium-native-theme.py

# Native status inset owner: no scrolling spacer or transparent web underlap.
python3 .circleci/scripts/apply-sandium-native-insets.py "$SRC"
python3 .circleci/scripts/apply-sandium-native-insets.py "$SRC" --verify-only

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

# Settings owns scoped fade resources, not shared app-wide axis animations.
python3 .circleci/scripts/apply-sandium-settings-fade.py --src "$SRC" --core "$CORE"
python3 .circleci/scripts/apply-sandium-settings-fade.py --src "$SRC" --core "$CORE" --verify-only
python3 .circleci/scripts/test-sandium-settings-fade.py

# Bounded opt-in geometry diagnostics only; does not fix loading-bar appearance.
python3 .circleci/scripts/apply-sandium-progress-diagnostics.py --src "$SRC"
python3 .circleci/scripts/apply-sandium-progress-diagnostics.py --src "$SRC" --verify-only
python3 .circleci/scripts/test-sandium-progress-diagnostics.py

# Native bottom-ranked suggestion groups after omnibox composition.
python3 .circleci/scripts/apply-sandium-suggestion-anchor.py "$SRC"
python3 .circleci/scripts/apply-sandium-suggestion-anchor.py "$SRC" --verify-only
python3 .circleci/scripts/test-sandium-suggestion-anchor.py

# Scoped audited Brave UI-link suppression; operational services unchanged.
python3 .circleci/scripts/apply-sandium-ui-links.py --core "$CORE" --src "$SRC"
python3 .circleci/scripts/test-sandium-ui-links.py --core "$CORE" --src "$SRC"

# Fixed high-contrast native switch palette, after Shields and native theme.
python3 .circleci/scripts/apply-sandium-oppo-toggles.py "$SRC" "$CORE"
python3 .circleci/scripts/test-sandium-oppo-toggles.py

# External-service-only Autofill, retaining profile data and native provider confirmations.
python3 .circleci/scripts/apply-sandium-autofill-off.py "$SRC"
python3 .circleci/scripts/apply-sandium-autofill-off.py "$SRC" --verify-only
python3 .circleci/scripts/test-sandium-autofill-off.py

# Browser-global Secure DNS controls over Chromium's native resolver.
python3 .circleci/scripts/apply-sandium-secure-dns.py "$SRC"
python3 .circleci/scripts/apply-sandium-secure-dns.py "$SRC" --verify-only
python3 -m unittest discover -s tests -p 'test_secure_dns_*.py'
