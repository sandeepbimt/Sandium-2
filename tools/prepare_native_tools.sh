#!/usr/bin/env bash
# Native candidate host tooling only; never upgrade already usable packages.
set -euo pipefail
JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
SYSTEM_PYTHON=/usr/bin/python3
missing=()
java_ready() {
  local version compiler
  version=$(timeout --signal=TERM --kill-after=5s 20s "$JAVA_HOME/bin/java" -version 2>&1) || return 1
  compiler=$(timeout --signal=TERM --kill-after=5s 20s "$JAVA_HOME/bin/javac" -version 2>&1) || return 1
  grep -Eq 'version "21([.\"]|$)' <<< "$version" && grep -Eq '^javac 21([.]|$)' <<< "$compiler"
}
if [[ -e "$JAVA_HOME/bin/java" || -e "$JAVA_HOME/bin/javac" ]]; then
  java_ready || { echo 'Existing Java 21 compiler/runtime is unusable; refusing automatic replacement' >&2; exit 1; }
else
  missing+=(openjdk-21-jdk-headless)
fi
command -v zstd >/dev/null && timeout --signal=TERM --kill-after=5s 20s zstd --version >/dev/null || missing+=(zstd)
[[ -x "$SYSTEM_PYTHON" ]] || { echo 'System Python is missing; refusing unreviewed host bootstrap' >&2; exit 1; }
timeout --signal=TERM --kill-after=5s 20s "$SYSTEM_PYTHON" -c 'import yaml' || missing+=(python3-yaml)
if ((${#missing[@]})); then
  # timeout runs as root, so TERM/KILL reach apt and its privileged children.
  # Lock wait is bounded separately; never remove package-manager locks.
  sudo -n timeout --signal=TERM --kill-after=20s 180s env DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=l apt-get -o DPkg::Lock::Timeout=30 update -qq
  sudo -n timeout --signal=TERM --kill-after=20s 300s env DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=l apt-get -o DPkg::Lock::Timeout=30 install -y --no-upgrade --no-install-recommends "${missing[@]}"
fi
# Recheck actual executables/imports, not merely apt exit status.
java_ready || { echo 'Java 21 capability verification failed' >&2; exit 1; }
timeout --signal=TERM --kill-after=5s 20s zstd --version >/dev/null
timeout --signal=TERM --kill-after=5s 20s "$SYSTEM_PYTHON" -c 'import yaml'
: "${BASH_ENV:?BASH_ENV is required}"
printf 'export JAVA_HOME=%q\nexport PATH=%q/bin:$PATH\n' "$JAVA_HOME" "$JAVA_HOME" >> "$BASH_ENV"
echo 'Native host tools verified; existing usable packages retained'
