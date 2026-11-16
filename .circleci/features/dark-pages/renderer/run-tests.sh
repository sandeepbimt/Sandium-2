#!/usr/bin/env bash
# Local source and extracted-native-helper tests only; no CI/publication actions.
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
python="${PYTHON:-python3}"
for test in test_renderer.py test_commit_constructors.py test_policy_native.py test_commit_native.py test_activation_native.py test_palette_native.py test_manual_native.py test_style_policy_native.py; do
  "$python" "$root/$test"
done
