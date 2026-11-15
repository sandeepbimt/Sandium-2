#!/usr/bin/env python3
"""Pinned unified address bar overlay, applied AFTER native bottom toolbar.

Native omnibox remains the only editable URL and the sole owner of security,
suggestions, focus, clipboard, voice, selection and IME behavior.
"""
from pathlib import Path
import importlib.util

spec = importlib.util.spec_from_file_location('bottom', Path(__file__).with_name('apply-sandium-bottom-toolbar.py'))
bottom = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bottom)
once = bottom.once
MARKER = 'SANDIUM_UNIFIED_ADDRESS_V1'
MODEL = bottom.BASE + 'java/src/org/chromium/chrome/browser/toolbar/LocationBarModel.java'


def model(s):
    if MARKER in s:
        return s
    return once(s, '            return buildUrlBarData(gurl, false, formattedUrl);', '''            // SANDIUM_UNIFIED_ADDRESS_V1: only ordinary, non-rewritten web URLs.
            // Preserve native IDN/spoof formatting and meaningful subdomains/ports. This
            // display string is NEVER used for navigation, clipboard or URL editing.
            // Earlier offline, publisher, frozen and special-page paths stay untouched.
            if ("https".equals(gurl.getScheme()) || "http".equals(gurl.getScheme())) {
                String identity = org.chromium.components.url_formatter.UrlFormatter
                        .formatUrlForDisplayOmitSchemePathAndTrivialSubdomains(gurl);
                return buildUrlBarData(gurl, false, identity, formattedUrl);
            }
            return buildUrlBarData(gurl, false, formattedUrl);''')


def phone(s):
    if MARKER in s:
        return s
    # Paint one enclosing surface without reparenting any security, click or edit target.
    # Native expansion fraction means focus/IME animation retains native field geometry.
    old = '''        // Brave's real Shields row precedes the new-tab slot. Extend paint only, never URL
        // touch/edit bounds; native focus expansion hides the row and retains its clear/go controls.
        View shields = findViewById(R.id.sandium_shields_row);
        if (shields != null) {
            int extension = Math.round(shields.getWidth()
                    * (1f - getExpansionFractionForVisualState(visualState)));
            if (LocalizationUtils.isLayoutRtl()) out.left -= extension;
            else out.right += extension;
        }'''
    new = '''        // SANDIUM_UNIFIED_ADDRESS_V1: one painted surface around native controls.
        // Keep their distinct hit targets, Page Info/security state and focus animations.
        // Never widen the editable URL over the action buttons.
        float sandiumRest = 1f - getExpansionFractionForVisualState(visualState);
        int sandiumInset = Math.round(4 * getResources().getDisplayMetrics().density);
        View sandiumLeading = findViewById(R.id.sandium_shields_row);
        if (sandiumLeading != null) {
            sandiumLeading.setAlpha(sandiumRest);
            if (sandiumLeading.getVisibility() != GONE) {
                sandiumLeading.setVisibility(urlHasFocus() || sandiumRest == 0f
                        ? INVISIBLE : VISIBLE);
            }
        }
        out.left = Math.round(out.left + (sandiumInset - out.left) * sandiumRest);
        out.right = Math.round(out.right
                + (getWidth() - sandiumInset - out.right) * sandiumRest);'''
    return once(s, old, new)


def menu_resource():
    return '''<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="24dp" android:height="24dp" android:viewportWidth="24" android:viewportHeight="24">
    <path android:fillColor="#FFFFFFFF" android:pathData="M12,4 a2,2 0,1 0,0.01,0 Z M12,10 a2,2 0,1 0,0.01,0 Z M12,16 a2,2 0,1 0,0.01,0 Z" />
</vector>
'''

OMNIBOX = 'chrome/browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/'


def location_phone(s):
    if MARKER in s:
        return location_scroll_ownership(s)
    # Reuse upstream's complete constraints, fit measurement, long-origin scrolling,
    # accessibility click forwarding, and focused restoration. Do not enable unrelated
    # toolbar experiments globally or center a clipped TextView over the omnibox.
    s = once(s, '            if (isToolbarUiRefactorEnabled() || wasCentering) {',
             '            if (mIsCenteringApplied || isToolbarUiRefactorEnabled() || wasCentering) {')
    s = once(s, '''        // Only apply centering if the experimental flag is enabled.
        if (!isToolbarUiRefactorEnabled()) {
            return false;
        }
''', '''        // SANDIUM_UNIFIED_ADDRESS_V1: native centering for this phone view only.
        // The native long-origin scrolling and focus restoration remain authoritative.
''')
    s = once(s, '        if (isToolbarUiRefactorEnabled()) {\n            mUrlObserver =',
             '        { // Sandium centering tracks same-tab navigation and title/identity changes.\n            mUrlObserver =')
    s = once(s, '        super.onFinishInflate();',
             '        super.onFinishInflate();\n        setClickable(true);\n        setLongClickable(true);')
    # Sandium's actions live OUTSIDE LocationBarPhone and were already subtracted
    # by ToolbarPhone. Native 48dp centering reserves belong to optional internal
    # actions in the experimental layout; reserving them again wastes 96dp.
    s = once(s, '            buttonSpace = Math.max(buttonSpace, mCenteringSpacePx);',
             '            buttonSpace = Math.max(buttonSpace, 0); // External actions already reserved.')
    # Native measurement clamps to a minimum, inappropriate when many actions share
    # a small toolbar. Never allow URL width to consume adjacent controls' hit regions.
    s = once(s, '            maxUrlWidth = Math.max(mMinUrlWidthPx, maxUrlWidth);',
             '            maxUrlWidth = Math.max(1, maxUrlWidth);')
    return location_scroll_ownership(s)


def location_scroll_ownership(s):
    if 'SANDIUM_URLBAR_LAYOUT_OWNERSHIP_V1' in s:
        return s
    # Center the measured UrlBar VIEW using the packed constraint chain above,
    # not its editable TextView internals. UrlBar owns horizontal wrapping,
    # focus/BiDi alignment, TLD visibility and scroll restoration. Overriding
    # those from parent measurement conflicts with the native layout contract.
    # #1171 tripped its invariant when scrollDisplayText requested another layout.
    start = s.index('        updateUrlBarAlignmentAndGravity(centeringApplied, fitsInCenteringSpace);')
    end = s.index('        if (centeringApplied) {', start)
    s = s[:start] + """        // SANDIUM_URLBAR_LAYOUT_OWNERSHIP_V1: packed VIEW centering only.
        // Do not mutate native text alignment, horizontal scrolling or scrollX here.
        // Native UrlBar maintains focus, BiDi and origin visibility invariants.

""" + s[end:]
    start = s.index('    /**\n     * Updates the UrlBar\'s text alignment and gravity')
    end = s.index('    /** Calculates the maximum allowed width', start)
    s = s[:start] + s[end:]
    s = once(s, '''     * <p>If the URL fits, horizontal scrolling is disabled to prevent visual misalignment, and its
     * scroll is reset to (0, 0).
     *
     * <p>If the URL does not fit, it is start-aligned, horizontal scrolling is enabled to allow
     * navigating the full text, and its layout width is capped.''', '''     * <p>Sandium centers the measured view using its packed constraint chain. Native UrlBar
     * owns text alignment, wrapping and origin scrolling for both fitting and long text.
     * Parent measurement changes only the available view width, not the text behavior.''')
    return s


def layout(s):
    if MARKER in s:
        return s
    start = s.index('<FrameLayout android:id="@+id/sandium_shields_row"')
    end = s.index('</FrameLayout>', start) + len('</FrameLayout>')
    row = s[start:end]
    row = once(row, 'android:layout_width="wrap_content" android:layout_height="wrap_content"',
               'android:layout_width="48dp" android:layout_height="48dp" '
               'android:layout_gravity="top|start" android:layout_marginStart="48dp"')
    s = s[:start] + s[end:]
    import re
    home = re.search(r'    <org\.chromium\.chrome\.browser\.toolbar\.home_button\.HomeButton[\s\S]*?/>', s)
    if home is None:
        raise ValueError('Pinned Home/Forward element missing')
    home_text = home.group(0)
    s = s[:home.start()] + s[home.end():]
    location = re.search(r'    <org\.chromium\.chrome\.browser\.omnibox\.LocationBarPhone[\s\S]*?/>', s)
    if location is None:
        raise ValueError('Pinned native location bar missing')
    # Both rendering paths paint before controls: background View (refactor) then
    # location_bar (legacy drawLocationBar paints its background), then actions.
    return s[:location.end()] + ('\n\n    <!-- SANDIUM_UNIFIED_ADDRESS_V1: controls after both background paths. -->\n'
            + home_text + '\n    ' + row) + s[location.end():]



def phone_leading_shield(s):
    if 'SANDIUM_LEADING_SHIELD_V1' in s:
        return s
    s = once(s, '        return padding;\n    }', '''        // SANDIUM_LEADING_SHIELD_V1: reserve actual start-slot width, including RTL.
        View sandiumShield = findViewById(R.id.sandium_shields_row);
        if (sandiumShield != null && sandiumShield.getVisibility() != GONE) {
            padding += sandiumShield.getMeasuredWidth();
        }
        return padding;
    }''')
    s = once(s, '        return (child == mHomeButton) ^ LocalizationUtils.isLayoutRtl();',
             '        return (child == mHomeButton || child.getId() == R.id.sandium_shields_row)\n'
             '                ^ LocalizationUtils.isLayoutRtl();')
    s = once(s, '''        if (mHomeButton.getVisibility() != GONE) {
            drawChild(canvas, mHomeButton, SystemClock.uptimeMillis());
        }
''', '')
    s = once(s, '        // Translate to draw end toolbar buttons.', '''        if (mHomeButton.getVisibility() != GONE) {
            drawChild(canvas, mHomeButton, SystemClock.uptimeMillis());
        }
        View sandiumShield = findViewById(R.id.sandium_shields_row);
        if (sandiumShield != null && sandiumShield.getVisibility() == VISIBLE) {
            drawChild(canvas, sandiumShield, SystemClock.uptimeMillis());
        }

        // Translate to draw end toolbar buttons.''')
    return s


def phone_shield_state(s):
    if 'SANDIUM_LEADING_SHIELD_STATE_V1' in s:
        return s
    s = once(s, '    private void updateSandiumForwardState() {', '''    private void updateSandiumForwardState() {
        updateSandiumLeadingShield();
    }

    // SANDIUM_LEADING_SHIELD_STATE_V1: search-engine status remains native on NTP.
    // Do not make the Shield stand in for transport/security/Page Info status.
    private void updateSandiumLeadingShield() {
        View row = findViewById(R.id.sandium_shields_row);
        if (row != null) {
            var tab = mSandiumObservedTab;
            boolean web = tab != null && ("https".equals(tab.getUrl().getScheme())
                    || "http".equals(tab.getUrl().getScheme()));
            // INVISIBLE reserves geometry but removes the entire child subtree from
            // hit-testing immediately. Both state and paint paths respect focus,
            // including measurements that do not recalculate background bounds.
            row.setVisibility(web && !isInTabSwitcherMode()
                    ? (urlHasFocus() ? INVISIBLE : VISIBLE) : GONE);
            android.view.ViewGroup.MarginLayoutParams params =
                    (android.view.ViewGroup.MarginLayoutParams) row.getLayoutParams();
            int margin = Math.round(48 * getResources().getDisplayMetrics().density);
            if (params.getMarginStart() != margin) {
                params.setMarginStart(margin);
                row.setLayoutParams(params);
            }
            row.setImportantForAccessibility(row.getVisibility() == VISIBLE && !urlHasFocus()
                    ? IMPORTANT_FOR_ACCESSIBILITY_AUTO
                    : IMPORTANT_FOR_ACCESSIBILITY_NO_HIDE_DESCENDANTS);
        }''')
    s = once(s, '        mHomeButton.setClickable(!hasFocus);',
             '        mHomeButton.setClickable(!hasFocus);\n        updateSandiumLeadingShield();')
    s = once(s, '        mTabSwitcherState = inTabSwitcherMode ? ENTERING_TAB_SWITCHER : EXITING_TAB_SWITCHER;',
             '        mTabSwitcherState = inTabSwitcherMode ? ENTERING_TAB_SWITCHER : EXITING_TAB_SWITCHER;\n        updateSandiumLeadingShield();')
    s = once(s, '        ViewUtils.requestLayout(this, "ToolbarPhone.onTabSwitcherTransitionFinished");',
             '        updateSandiumLeadingShield();\n        ViewUtils.requestLayout(this, "ToolbarPhone.onTabSwitcherTransitionFinished");')
    return s


def brave(s):
    if 'SANDIUM_UNIFIED_SHIELD_PAINT_V1' in s:
        return s
    # The phone row is now a root child and gets its own animation drawing path.
    s = once(s, '        if (mShieldsLayout != null && mShieldsLayout.getVisibility() != View.GONE) {',
             '        // SANDIUM_UNIFIED_SHIELD_PAINT_V1: phone leading row is drawn by ToolbarPhone.\n'
             '        if (findViewById(R.id.sandium_shields_row) == null\n'
             '                && mShieldsLayout != null && mShieldsLayout.getVisibility() != View.GONE) {')
    # Avoid a second segmented background but never null it: existing native tint
    # paths dereference the background and must remain safe during initialization.
    s = once(s, '''        if (mShieldsLayout == null || mBraveButtonsInLocationBar) {
            return;
        }''', '''        if (mShieldsLayout == null || mBraveButtonsInLocationBar) {
            return;
        }
        if (findViewById(R.id.sandium_shields_row) != null) {
            mShieldsLayout.setBackgroundColor(android.graphics.Color.TRANSPARENT);
            return;
        }''')
    # Color filter would turn the transparent segment opaque; leave unified paint owner.
    s = once(s, '        if (mBraveButtonsInLocationBar) {',
             '        if (mBraveButtonsInLocationBar || findViewById(R.id.sandium_shields_row) != null) {')
    return s


def responsive(s):
    if 'SANDIUM_COMPACT_UNIFIED_V1' in s:
        return s
    s = once(s, '    private ImageView mHomeButton;', """    private ImageView mHomeButton;
    // SANDIUM_COMPACT_UNIFIED_V1: preserve identity and 48dp targets before convenience.
    // Only New tab collapses on narrow windows; it remains available in the menu.
    private int mSandiumToolbarWidthPx;
    private boolean sandiumCompactToolbar() {
        float density = getResources().getDisplayMetrics().density;
        float widthDp = mSandiumToolbarWidthPx > 0 ? mSandiumToolbarWidthPx / density
                : getResources().getConfiguration().screenWidthDp;
        return widthDp < 360 || getResources().getConfiguration().fontScale > 1.3f;
    }
""")
    s = once(s, '''        if (mDestroyChecker.isDestroyed()) {
            super.onMeasure(widthMeasureSpec, heightMeasureSpec);
            return;
        }''', """        if (mDestroyChecker.isDestroyed()) {
            super.onMeasure(widthMeasureSpec, heightMeasureSpec);
            return;
        }
        mSandiumToolbarWidthPx = MeasureSpec.getSize(widthMeasureSpec);
        View sandiumNewTab = findViewById(R.id.sandium_new_tab);
        if (sandiumNewTab != null) {
            sandiumNewTab.setVisibility(sandiumCompactToolbar() ? GONE : VISIBLE);
        }
        if (mLocationBar != null) {
            mHomeButton.setVisibility(urlHasFocus() ? INVISIBLE : VISIBLE);
            updateSandiumLeadingShield();
        }""")
    return s


def position(s):
    if 'SANDIUM_FOCUSED_BOTTOM_V1' in s:
        return s
    return once(s, """        if (ntpShowing
                || tabSwitcherShowing
                || isOmniboxFocused
                || isFindInPageShowing""", """        // SANDIUM_FOCUSED_BOTTOM_V1: when bottom is the selected position, retain
        // it while editing. Existing focused-bottom IME offset, resize mode,
        // keyboard accessory and maximum-height safeguards remain authoritative.
        // Hub, Find, PiP and explicit top preference still use the native fallback.
        if ((ntpShowing && !isOmniboxFocused)
                || tabSwitcherShowing
                || isFindInPageShowing""")


def all_phone(s):
    return responsive(phone_shield_state(phone_leading_shield(phone(s))))


def transformations(src, core):
    return [(src / bottom.PHONE, all_phone), (src / MODEL, model),
            (src / bottom.BASE / 'java/src/org/chromium/chrome/browser/toolbar/ToolbarPositionController.java', position),
            (src / OMNIBOX / 'LocationBarPhone.java', location_phone),
            (src / bottom.BASE / 'java/res/layout/toolbar_phone.xml', layout),
            (core / bottom.BRAVE, brave)]


def verify(src, core):
    for p, transform in transformations(src, core):
        text = p.read_text()
        if transform(text) != text:
            raise ValueError('Unified address transformation missing: ' + str(p))
    asset = src / bottom.BASE / 'java/res/drawable/sandium_toolbar_menu.xml'
    if asset.read_text() != menu_resource():
        raise ValueError('Unified address menu asset mismatch')


def apply(src, core):
    import subprocess
    if subprocess.check_output(['git', '-C', str(src), 'rev-parse', 'HEAD'], text=True).strip() != bottom.PIN:
        raise ValueError('Unexpected Chromium pin')
    if subprocess.check_output(['git', '-C', str(core), 'rev-parse', 'HEAD'], text=True).strip() != bottom.BRAVE_PIN:
        raise ValueError('Unexpected Brave pin')
    changes = transformations(src, core)
    output = [(p, f(p.read_text())) for p, f in changes]
    output.append((src / bottom.BASE / 'java/res/drawable/sandium_toolbar_menu.xml', menu_resource()))
    for p, text in output:
        p.write_text(text)


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--src', type=Path, required=True)
    p.add_argument('--core', type=Path, required=True)
    p.add_argument('--verify-only', action='store_true')
    a = p.parse_args()
    if a.verify_only:
        verify(a.src, a.core)
    else:
        apply(a.src, a.core)
