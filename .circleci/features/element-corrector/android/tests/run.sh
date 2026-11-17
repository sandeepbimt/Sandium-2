#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
java_bin="${JAVA_HOME:+$JAVA_HOME/bin/}java"
out="$(mktemp -d)"
trap 'rm -rf "$out"' EXIT
python3 - "$root" "$out" <<'PYGEN'
import importlib.util, pathlib, sys
root,out=map(pathlib.Path,sys.argv[1:])
spec=importlib.util.spec_from_file_location('chooser_apply',root/'apply.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
body=m.handler('        setupAdvancedOptionsListeners();\n')
source='import android.content.Context;\nimport android.view.View;\nimport org.chromium.chrome.browser.tab.Tab;\nclass ShieldListenerCompile {\n Context mContext; Tab mCurrentTab; View popupView;\n static class R {static class id {static final int sandium_element_colors_button=1;}}\n void hide(){} void setupAdvancedOptionsListeners(){}\n void setupViews(){\n  Context context=mContext;\n' + body + "\n }\n}\n"
(out/'ShieldListenerCompile.java').write_text(source)
PYGEN
mapfile -t sources < <(find "$root/tests/stubs" -name '*.java' -print)
"$java_bin" com.sun.tools.javac.Main -d "$out" "${sources[@]}" "$root/java/org/chromium/chrome/browser/sandium/dark/SandiumElementColorsUtils.java" "$root/tests/ElementChooserTest.java" "$out/ShieldListenerCompile.java"
"$java_bin" -cp "$out" org.chromium.chrome.browser.sandium.dark.ElementChooserTest
