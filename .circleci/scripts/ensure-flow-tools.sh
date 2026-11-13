#!/usr/bin/env bash
set -euo pipefail
# APT packages belong to Ubuntu's system Python, not CircleCI's PATH/pyenv Python.
# Only seed configuration tests need PyYAML. Do not change build/helper Python PATH.
SYSTEM_PYTHON=/usr/bin/python3
WITH_TEST_TOOLS=false
case "${1:-}" in
  '') ;;
  --with-test-tools) WITH_TEST_TOOLS=true ;;
  *) echo "FLOW_TOOLS=FAIL unknown argument: $1" >&2; exit 2 ;;
esac
printf 'FLOW_PATH_PYTHON=%s\n' "$(command -v python3 || true)"
python3 -c 'import sys; print("FLOW_PATH_PYTHON_RUNTIME=" + sys.executable + " " + sys.version.split()[0])'
packages=()
command -v zstd >/dev/null 2>&1 || packages+=(zstd)
command -v tar >/dev/null 2>&1 || packages+=(tar)
if [ "$WITH_TEST_TOOLS" = true ]; then
  if [ ! -x "$SYSTEM_PYTHON" ]; then
    packages+=(python3 python3-yaml)
  elif ! "$SYSTEM_PYTHON" -c 'import yaml' >/dev/null 2>&1; then
    packages+=(python3-yaml)
  fi
fi
if [ "${#packages[@]}" -gt 0 ]; then
  sudo apt-get update -qq
  sudo apt-get install -y "${packages[@]}"
fi
command -v zstd
command -v tar
if [ "$WITH_TEST_TOOLS" = true ]; then
  "$SYSTEM_PYTHON" -c 'import sys,yaml; print("FLOW_TEST_PYTHON=" + sys.executable + " " + sys.version.split()[0]); print("FLOW_TEST_YAML=" + yaml.__file__)'
fi
echo "FLOW_TOOLS=PASS test_tools=$WITH_TEST_TOOLS"
