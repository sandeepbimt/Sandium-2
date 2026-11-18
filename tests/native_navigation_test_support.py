"""Explicit product exceptions and Settings seeds, never rewrite pinned sources."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SETTINGS=json.loads((ROOT/'experiments/native-navigation/settings-reversal.json').read_text())
STARTUP_PATH='chrome/android/java/src/org/chromium/chrome/browser/base/SplitCompatApplication.java'
NATIVE_BLUR_STARTUP='            // Native Chromium navigation: enable blur without custom field-trial params.\n            // Saved Sandium strength/darken preferences are deliberately inert.\n            final CommandLine nativeBlurCommandLine = CommandLine.getInstance();\n            final String nativeBlurFeature = "AndroidNavigationBlurTransitionAnimation";\n            if (!containsSandiumFeature(nativeBlurCommandLine.getSwitchValue(\n                        "disable-features", ""), nativeBlurFeature)) {\n                final StringBuilder nativeBlurEnabled = new StringBuilder();\n                for (String entry : nativeBlurCommandLine.getSwitchValue(\n                            "enable-features", "").split(",")) {\n                    final String trimmed = entry.trim();\n                    if (!trimmed.isEmpty() && !nativeBlurFeature.equals(\n                                getSandiumFeatureName(trimmed))) {\n                        if (nativeBlurEnabled.length() > 0) nativeBlurEnabled.append(\',\');\n                        nativeBlurEnabled.append(trimmed);\n                    }\n                }\n                if (nativeBlurEnabled.length() > 0) nativeBlurEnabled.append(\',\');\n                nativeBlurEnabled.append(nativeBlurFeature);\n                nativeBlurCommandLine.appendSwitchWithValue(\n                        "enable-features", nativeBlurEnabled.toString());\n            }'

def seed_settings(root):
 for path,pairs in SETTINGS.items():
  p=root/path;p.parent.mkdir(parents=True,exist_ok=True)
  p.write_text('\n'.join(after for before,after in pairs))

def expected_native(path,pinned):
 if path == STARTUP_PATH:
  return pinned.replace('            // Native-navigation comparison: use pinned feature defaults.', NATIVE_BLUR_STARTUP)
 if path.endswith('/TabWebContentsDelegateAndroidImpl.java'):
  return pinned.replace('R.drawable.chromelogo16', 'R.drawable.sandium_toolbar_mark')
 return pinned
