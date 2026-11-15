#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
out=$(mktemp -d)
trap 'rm -rf "$out"' EXIT
java com.sun.tools.javac.Main -d "$out" \
 java/org/chromium/chrome/browser/sandium/video/*.java \
 $(find tests/stubs -name '*.java' ! -name 'NativeVideoGeometryBridgeJni.java') \
 tests/GestureStateTest.java tests/GestureViewContractTest.java tests/VideoOwnerContractTest.java tests/VideoThemeTest.java
java -cp "$out" GestureStateTest
java -cp "$out" GestureViewContractTest
java -cp "$out" VideoOwnerContractTest

java -cp "$out" VideoThemeTest
