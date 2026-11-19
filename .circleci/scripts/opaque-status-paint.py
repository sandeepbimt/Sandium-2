#!/usr/bin/env python3
"""Plan opaque native status backing after native inset restoration; no writer."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
CHANGES = json.loads((ROOT / '.circleci/features/opaque-status-paint/patches.json').read_text())
FILES = tuple(dict.fromkeys(name for name, _, _ in CHANGES))
PAINT_PATHS = FILES

def transform(name, text):
    if name not in FILES:
        return text
    if 'mSandiumScrollUnderStatusBar' in text or 'mSandiumRestoringStatusBar' in text:
        raise RuntimeError('Native inset restoration must precede opaque paint: ' + name)
    changes = [entry for entry in CHANGES if entry[0] == name]
    # Chromium158 adds a TaskDescription background argument. Preserve it;
    # only the existing foreground/icon and opaque paint policy is overridden.
    if '            @ColorInt int taskDescriptionBackgroundColor) {' in text:
        variants = {
            '                mForceLightIconColorForNtp && isStandardNtp() && !mIsOmniboxFocused);': (
                '                mActivity,\n                statusBarColor,\n'
                '                mForceLightIconColorForNtp && isStandardNtp() && !mIsOmniboxFocused,\n'
                '                backgroundColor);',
                '                mActivity,\n                statusBarColor,\n'
                '                /* forceLightIconColor= */ false,\n'
                '                backgroundColor);'),
            '            boolean forceLightIconColor) {\n        Window window = activity.getWindow();': (
                '            boolean forceLightIconColor,\n'
                '            @ColorInt int taskDescriptionBackgroundColor) {\n'
                '        Window window = activity.getWindow();',
                '            boolean forceLightIconColor,\n'
                '            @ColorInt int taskDescriptionBackgroundColor) {\n'
                '        color = EdgeToEdgeSystemBarColorHelper.getSandiumOpaqueStatusColor(color);\n'
                '        Window window = activity.getWindow();'),
        }
        changes = [(path, *variants[old]) if old in variants else (path, old, new)
                   for path, old, new in changes]
    for _, old, new in reversed(changes):
        if text.count(new) == 1 and old not in text.replace(new, '', 1):
            text = text.replace(new, old, 1)
        elif new not in text and text.count(old) <= 1:
            pass
        else:
            raise RuntimeError('Unknown or duplicate opaque status paint: ' + name)
    if 'SANDIUM_OPAQUE_STATUS_PAINT' in text or 'getSandiumOpaqueStatusColor' in text:
        raise RuntimeError('Partial opaque status paint: ' + name)
    for _, old, new in changes:
        if text.count(old) != 1:
            raise RuntimeError('Opaque status source anchor mismatch: ' + name)
        text = text.replace(old, new, 1)
    return text

def plan(root):
    root = Path(root)
    return {root / name: transform(name, (root / name).read_text()) for name in FILES}
