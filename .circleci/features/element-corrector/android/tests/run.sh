#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
java_bin="${JAVA_HOME:+$JAVA_HOME/bin/}java"
out="$(mktemp -d)"
trap 'rm -rf "$out"' EXIT
mapfile -t sources < <(find "$root/java" "$root/tests/stubs" -name '*.java' -print)
"$java_bin" com.sun.tools.javac.Main -d "$out" "${sources[@]}" "$root/tests/ElementChooserTest.java"
"$java_bin" -cp "$out" org.chromium.chrome.browser.sandium.dark.ElementChooserTest
