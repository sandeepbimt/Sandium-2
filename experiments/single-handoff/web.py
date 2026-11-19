"""Ordinary web baseline: one native owner, no optional blur/fallback overlay.

Applies AFTER the pinned-native-navigation profile. Does not broaden paint
holding eligibility, delay navigation, retain cross-origin screenshots, or
replace Chromium's renderer/surface lifecycle with a second coordinator.
"""
import json
from pathlib import Path
PATH = 'chrome/android/java/src/org/chromium/chrome/browser/base/SplitCompatApplication.java'
ROOT = Path(__file__).resolve().parents[2]
OLD = next(p['new'] for p in json.loads(
    (ROOT/'experiments/native-navigation/patches.json').read_text())
    if p['path'] == PATH)
NEW = '            // SANDIUM_NATIVE_BLUR_158: toggle only, native timing/strength/lifecycle.\n            final android.content.SharedPreferences blurPrefs = ContextUtils.getAppSharedPreferences();\n            final String blurKey = "sandium_page_transition_blur_enabled";\n            boolean blurOn = true;\n            if (blurPrefs.contains(blurKey)) {\n                blurOn = blurPrefs.getBoolean(blurKey, true);\n            } else {\n                final String legacy = blurPrefs.getString("sandium_page_transition_blur_level", "on");\n                blurOn = !"default".equals(legacy) && !"off".equals(legacy);\n                blurPrefs.edit().putBoolean(blurKey, blurOn).apply();\n            }\n            final CommandLine handoffCommandLine = CommandLine.getInstance();\n            final String handoffBlurFeature = "AndroidNavigationBlurTransitionAnimation";\n            final String dimFeature = "SandiumNavigationTransitionDim";\n            for (String switchName : new String[] {"enable-features", "disable-features"}) {\n                final StringBuilder cleaned = new StringBuilder();\n                for (String entry : handoffCommandLine.getSwitchValue(switchName, "").split(",")) {\n                    final String trimmed = entry.trim();\n                    final String name = getSandiumFeatureName(trimmed);\n                    if (!trimmed.isEmpty() && !handoffBlurFeature.equals(name) && !dimFeature.equals(name)) {\n                        if (cleaned.length() > 0) cleaned.append(\',\');\n                        cleaned.append(trimmed);\n                    }\n                }\n                final boolean enable = "enable-features".equals(switchName);\n                if (enable == blurOn) {\n                    if (cleaned.length() > 0) cleaned.append(\',\');\n                    cleaned.append(handoffBlurFeature);\n                }\n                if (enable == (blurOn && blurPrefs.getBoolean("sandium_page_transition_darken", false))) {\n                    if (cleaned.length() > 0) cleaned.append(\',\');\n                    cleaned.append(dimFeature);\n                }\n                handoffCommandLine.appendSwitchWithValue(switchName, cleaned.toString());\n            }'

def transform(text):
    if text.count(NEW) == 1 and OLD not in text:
        return text
    if 'SANDIUM_NATIVE_BLUR_158' in text or text.count(OLD) != 1:
        raise ValueError('Ordinary web startup baseline drift; refusing partial change')
    return text.replace(OLD, NEW, 1)

def plan(root):
    p = Path(root)/PATH
    return {p: transform(p.read_text())}
