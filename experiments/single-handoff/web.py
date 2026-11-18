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
NEW = '''            // SANDIUM_SINGLE_HANDOFF_WEB_V1: keep ordinary surface/paint holding native.
            // The optional blur manager adds a timed solid-color intermediate stage.
            // Disable that manager; do not override native paint-holding policy.
            final CommandLine handoffCommandLine = CommandLine.getInstance();
            final String handoffBlurFeature = "AndroidNavigationBlurTransitionAnimation";
            final StringBuilder handoffEnabled = new StringBuilder();
            for (String entry : handoffCommandLine.getSwitchValue(
                        "enable-features", "").split(",")) {
                final String trimmed = entry.trim();
                if (!trimmed.isEmpty() && !handoffBlurFeature.equals(
                            getSandiumFeatureName(trimmed))) {
                    if (handoffEnabled.length() > 0) handoffEnabled.append(',');
                    handoffEnabled.append(trimmed);
                }
            }
            handoffCommandLine.appendSwitchWithValue(
                    "enable-features", handoffEnabled.toString());
            final StringBuilder handoffDisabled = new StringBuilder();
            for (String entry : handoffCommandLine.getSwitchValue(
                        "disable-features", "").split(",")) {
                final String trimmed = entry.trim();
                if (!trimmed.isEmpty() && !handoffBlurFeature.equals(
                            getSandiumFeatureName(trimmed))) {
                    if (handoffDisabled.length() > 0) handoffDisabled.append(',');
                    handoffDisabled.append(trimmed);
                }
            }
            if (handoffDisabled.length() > 0) handoffDisabled.append(',');
            handoffDisabled.append(handoffBlurFeature);
            handoffCommandLine.appendSwitchWithValue(
                    "disable-features", handoffDisabled.toString());'''

def transform(text):
    if text.count(NEW) == 1 and OLD not in text:
        return text
    if 'SANDIUM_SINGLE_HANDOFF_WEB_V1' in text or text.count(OLD) != 1:
        raise ValueError('Ordinary web startup baseline drift; refusing partial change')
    return text.replace(OLD, NEW, 1)

def plan(root):
    p = Path(root)/PATH
    return {p: transform(p.read_text())}
