#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
java_bin="${JAVA_HOME:+$JAVA_HOME/bin/}java"
out="$(mktemp -d)"
trap 'rm -rf "$out"' EXIT
"$java_bin" com.sun.tools.javac.Main -d "$out" \
  "$root/java/org/chromium/chrome/browser/sandium/text/PageTextPolicy.java" \
  "$root/java/org/chromium/chrome/browser/sandium/text/PageTextStylesheet.java" \
  "$root/tests/PageTextPolicyTest.java"
"$java_bin" -cp "$out" PageTextPolicyTest
