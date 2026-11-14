#!/usr/bin/env python3
"""Neutral app-chrome default, preserving native dynamic opt-in and non-browser activities."""
from pathlib import Path
import argparse

REL = 'chrome/browser/ui/android/theme/java/src/org/chromium/chrome/browser/theme/TopUiThemeColorProvider.java'
ANCHOR = '    private boolean isThemingAllowed(Tab tab) {\n'
REPLACEMENT = '''    private boolean isThemingAllowed(Tab tab) {
        // Sandium regular-browser chrome follows its app theme, never a webpage tint.
        // Preserve the native color+foreground pairing and explicit dynamic-color choice.
        // Custom tabs/WebAPKs/PWAs retain their distinct activity branding paths.
        android.content.Context context = mContext;
        while (context instanceof android.content.ContextWrapper
                && !(context instanceof android.app.Activity)) {
            android.content.Context base =
                    ((android.content.ContextWrapper) context).getBaseContext();
            if (base == context) break;
            context = base;
        }
        if ("ChromeTabbedActivity".equals(context.getClass().getSimpleName())) return false;
'''

BOTTOM_REL = REL.replace('TopUiThemeColorProvider.java', 'BottomUiThemeColorProvider.java')
BOTTOM_ANCHOR = '    private void updateColorAndTint(boolean animate) {\n        if (mIsBottomBarEnabled) {'
BOTTOM_REPLACEMENT = '    private void updateColorAndTint(boolean animate) {\n        // Sandium: regular browser toolbar follows the same app surface/tint pair\n        // even when the bottom stack has a differently colored feature layer.\n        android.content.Context context = mContext;\n        while (context instanceof android.content.ContextWrapper\n                && !(context instanceof android.app.Activity)) {\n            android.content.Context base =\n                    ((android.content.ContextWrapper) context).getBaseContext();\n            if (base == context) break;\n            context = base;\n        }\n        boolean sandiumRegularBrowser = !mIncognito\n                && "ChromeTabbedActivity".equals(context.getClass().getSimpleName());\n        if (mIsBottomBarEnabled && sandiumRegularBrowser) {\n            updatePrimaryColor(getColorForTopAnchoredToolbar(), animate);\n            ColorStateList tint = getTintForTopAnchoredToolbar();\n            updateTint(tint, tint, getBrandedColorSchemeForTopAnchoredToolbar());\n        } else if (mIsBottomBarEnabled) {'

def transform_bottom(source):
    if BOTTOM_REPLACEMENT in source:
        return source
    if source.count(BOTTOM_ANCHOR) != 1:
        raise ValueError('Pinned BottomUiThemeColorProvider seam changed')
    return source.replace(BOTTOM_ANCHOR, BOTTOM_REPLACEMENT, 1)

def transform(source):
    if REPLACEMENT in source:
        return source
    if source.count(ANCHOR) != 1:
        raise ValueError('Pinned TopUiThemeColorProvider theme seam changed')
    return source.replace(ANCHOR, REPLACEMENT, 1)

def apply(src):
    # Validate both providers before writing either one.
    outputs = {src / REL: transform((src / REL).read_text()),
               src / BOTTOM_REL: transform_bottom((src / BOTTOM_REL).read_text())}
    for path, text in outputs.items():
        path.write_text(text)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('src', type=Path)
    apply(parser.parse_args().src)
    print('SANDIUM_CHROME_THEME=PASS scope=regular-browser website-content=unchanged dynamic-choice=preserved')
