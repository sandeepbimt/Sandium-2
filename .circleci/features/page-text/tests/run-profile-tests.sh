#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
java_bin="${JAVA_HOME:+$JAVA_HOME/bin/}java"
: "${JSON_JAVA_JAR:?Set JSON_JAVA_JAR to JSON-java 20240303 jar}"
out="$(mktemp -d)"; trap 'rm -rf "$out"' EXIT
mapfile -t stubs < <(find "$root/../dark-pages/tests/stubs/org/chromium" -name '*.java' -print)
"$java_bin" com.sun.tools.javac.Main -cp "$JSON_JAVA_JAR" -d "$out" \
  "${stubs[@]}" \
  "$root/java/org/chromium/chrome/browser/sandium/text/PageTextPolicy.java" \
  "$root/java/org/chromium/chrome/browser/sandium/text/SandiumPageText.java" \
  "$root/tests/PageTextProfileTest.java"
"$java_bin" -cp "$out:$JSON_JAVA_JAR" PageTextProfileTest
