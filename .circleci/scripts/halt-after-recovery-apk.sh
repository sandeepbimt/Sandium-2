#!/usr/bin/env bash
# Only after APK verification, artifact publication, and saving its small status marker.
set -euo pipefail
[ "${CIRCLE_BRANCH:-}" = 'fix/1416-apk-recovery' ] || { echo "RECOVERY_APK_HALT=REFUSED wrong branch" >&2; exit 1; }
circleci-agent step halt
