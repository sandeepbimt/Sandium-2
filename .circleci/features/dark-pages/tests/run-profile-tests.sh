#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
java_bin="${JAVA_HOME:+$JAVA_HOME/bin/}java"
: "${JSON_JAVA_JAR:?Set JSON_JAVA_JAR to JSON-java 20240303 jar for host tests}"
out="$(mktemp -d)"
trap 'rm -rf "$out"' EXIT
mapfile -t sources < <(find "$root/java" "$root/tests/stubs" -name '*.java' -print)
"$java_bin" com.sun.tools.javac.Main -cp "$JSON_JAVA_JAR" -d "$out" \
  "${sources[@]}" "$root/tests/ProfilePolicyTest.java" "$root/tests/DialogPolicyTest.java"
"$java_bin" -cp "$out:$JSON_JAVA_JAR" ProfilePolicyTest
"$java_bin" -cp "$out:$JSON_JAVA_JAR" DialogPolicyTest
