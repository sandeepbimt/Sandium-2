# Siso requires an explicit credential helper in non-Google CI.
# Never enable xtrace here: BUILDBUDDY_API_KEY is a secret.
set -eu
if [ -z "$(printenv BUILDBUDDY_API_KEY 2>/dev/null || true)" ]; then
  echo "MISSING_REQUIRED_SECRET=BUILDBUDDY_API_KEY" >&2
  echo "Set BUILDBUDDY_API_KEY in CircleCI project environment variables." >&2
  exit 1
fi
HELPER=/tmp/sandium-buildbuddy-credential-helper.py
printf '%s\n' \
  '#!/usr/bin/env python3' \
  'import json' \
  'import os' \
  'import sys' \
  '' \
  'if len(sys.argv) < 2 or sys.argv[1] != "get":' \
  '    raise SystemExit(1)' \
  'sys.stdin.read()' \
  'key = os.environ["BUILDBUDDY_API_KEY"]' \
  'print(json.dumps({"headers": {"x-buildbuddy-api-key": [key]}}))' \
  > "$HELPER"
chmod 700 "$HELPER"
echo 'export SISO_CREDENTIAL_HELPER=/tmp/sandium-buildbuddy-credential-helper.py' >> "$BASH_ENV"
# Brave v1.98.62 installs depot_tools at vendor/depot_tools relative to src/brave.
# Keep this separate from the Afterbird sibling checkout layout.
echo 'export PATH="$CIRCLE_WORKING_DIRECTORY/brave-work/src/brave/vendor/depot_tools:$PATH"' >> "$BASH_ENV"
echo 'export DEPOT_TOOLS_UPDATE=0' >> "$BASH_ENV"
echo 'export SISO_LIMITS=local=8,remote=80' >> "$BASH_ENV"
echo "SISO_CREDENTIAL_HELPER=CONFIGURED (secret value not printed)"
