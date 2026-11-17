#!/usr/bin/env python3
"""Remove Brave's startup video promotion, including restored dialog state."""
import argparse
from pathlib import Path

JAVA = 'android/java/org/chromium/chrome/browser/'
ACTIVITY = JAVA + 'app/BraveActivity.java'
FRAGMENT = JAVA + 'BraveAdFreeCalloutDialogFragment.java'
MARKER = '// Sandium: no startup video promotion.'


def activity(source):
    start = '    private void showAdFreeCalloutDialog() {'
    end = '    public void setNewTabPageManager('
    if source.count(start) != 1 or source.count(end) != 1:
        raise ValueError('pinned video promo activity anchors changed')
    a, b = source.index(start), source.index(end)
    old = source[a:b]
    if MARKER not in old and 'new BraveAdFreeCalloutDialogFragment()' not in old:
        raise ValueError('unexpected video promo launch body')
    new = '''    private void showAdFreeCalloutDialog() {
        // Sandium: no startup video promotion.
        ChromeSharedPreferences.getInstance()
                .writeBoolean(BravePreferenceKeys.BRAVE_AD_FREE_CALLOUT_DIALOG, false);
    }

'''
    return source[:a] + new + source[b:]


def fragment(source):
    # Keep the class identity so FragmentManager can safely restore saved state
    # from older APKs, but never create a window or inflate promotional content.
    header, sep, rest = source.partition('package org.chromium.chrome.browser;')
    if not sep or 'class BraveAdFreeCalloutDialogFragment' not in rest:
        raise ValueError('pinned video promo fragment identity changed')
    return header + '''package org.chromium.chrome.browser;

import android.os.Bundle;

import org.chromium.build.annotations.NullMarked;
import org.chromium.build.annotations.Nullable;

/** Compatibility tombstone for promotional fragments saved by older APKs. */
@NullMarked
public class BraveAdFreeCalloutDialogFragment extends BraveDialogFragment {
    @Override
    public void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        // Sandium: no startup video promotion.
        setShowsDialog(false);
    }

    @Override
    public void onResume() {
        super.onResume();
        dismissAllowingStateLoss();
    }
}
'''


def apply(core):
    changes = {ACTIVITY: activity((core / ACTIVITY).read_text()),
               FRAGMENT: fragment((core / FRAGMENT).read_text())}
    for relative, content in changes.items():
        (core / relative).write_text(content)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core', type=Path, required=True)
    args = parser.parse_args()
    apply(args.core)
    print('SANDIUM_NO_VIDEO_PROMO=PASS')
