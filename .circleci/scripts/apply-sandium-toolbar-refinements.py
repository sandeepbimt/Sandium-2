#!/usr/bin/env python3
"""#1171 device-feedback corrections, after the unified-address overlay.

Keep native transport warnings, native Page Info menu dispatch, native tab callbacks,
and the editable UrlBar's text/scroll ownership. No synthetic URL or JS input.
"""
from pathlib import Path
import argparse
import importlib.util
import subprocess

spec = importlib.util.spec_from_file_location('bottom', Path(__file__).with_name('apply-sandium-bottom-toolbar.py'))
bottom = importlib.util.module_from_spec(spec); spec.loader.exec_module(bottom)
def once(s, old, new):
    if new in s: return s
    if s.count(old) != 1: raise ValueError('Toolbar refinement anchor mismatch: ' + old[:100])
    return s.replace(old, new, 1)
TOP = bottom.BASE + 'java/src/org/chromium/chrome/browser/toolbar/top/'
UTIL = 'chrome/browser/util/android/java/src/org/chromium/chrome/browser/util/BrowserUiUtils.java'
DIMENS = 'chrome/browser/ui/android/omnibox/java/res/values/dimens.xml'


def phone(s):
    # Keep the existing new-tab action alive as a private dispatch target, but no
    # longer expose a second + or reserve any width for it in any window/font state.
    return once(s, 'sandiumNewTab.setVisibility(sandiumCompactToolbar() ? GONE : VISIBLE);',
                'sandiumNewTab.setVisibility(GONE); // SANDIUM_TAB_DUAL_ACTION_V1: no duplicate + slot.')


def layout(s):
    return once(s, 'android:id="@+id/sandium_new_tab"\n',
                'android:id="@+id/sandium_new_tab"\n            android:visibility="gone"\n            android:importantForAccessibility="noHideDescendants"\n')


def page_info(s):
    # Use the existing end-to-end Chromium/Brave relocation path instead of simply
    # deleting the security widget. HTTP/certificate/error indications stay visible;
    # Page Info becomes a real native menu item, separate from the unchanged Shield.
    return once(s, '''        return ChromeFeatureList.sAndroidPageInfoAsAppMenuItem.isEnabled()
                && !DeviceFormFactor.isNonMultiDisplayContextOnTablet(context);''',
                '''        // SANDIUM_PAGE_INFO_IN_MENU_V1: recover the ordinary tune-icon slot.
        // Native StatusMediator retains non-secure/permission indications.
        return !DeviceFormFactor.isNonMultiDisplayContextOnTablet(context);''')


def dimens(s):
    return once(s, '<dimen name="location_bar_url_text_size">16sp</dimen>',
                '<dimen name="location_bar_url_text_size">14.4sp</dimen>')


def coordinator(s):
    s = once(s, '''        mToggleTabStackButton.setOnClickListener(onClickListener);
        mToggleTabStackButton.setOnLongClickListener(onLongClickListener);''', '''        // SANDIUM_TAB_DUAL_ACTION_V1: scope only to the Sandium phone row.
        View sandiumNewTab = mToggleTabStackButton.getRootView().findViewById(R.id.sandium_new_tab);
        if (sandiumNewTab != null) {
            mToggleTabStackButton.setSandiumDualAction(true);
            mToggleTabStackButton.setOnClickListener(v -> {
                if (!v.isEnabled() || !v.isClickable()) return;
                // Reuse Brave's existing native dispatcher and current incognito policy.
                sandiumNewTab.performClick();
            });
            mToggleTabStackButton.setOnLongClickListener(v -> {
                if (!v.isEnabled() || !v.isClickable()) return false;
                onClickListener.onClick(v); // Original switcher action, not a new-tab popup.
                return true; // Consume release; never open a new tab after holding.
            });
        } else {
            mToggleTabStackButton.setOnClickListener(onClickListener);
            mToggleTabStackButton.setOnLongClickListener(onLongClickListener);
        }''')
    s = once(s, '        mToggleTabStackButton.setSuppliers(tabCountSupplier);', '''        mToggleTabStackButton.setSuppliers(tabCountSupplier);
        if (mToggleTabStackButton.isSandiumDualAction() && tabCountSupplier.get() != null) {
            mToggleTabStackButton.onDrawableStateChanged();
        }''')
    s = once(s, '''        // Enable tab switcher button.
        mToggleTabStackButton.setClickable(true);''', '''        // Enable both actions after native tab restoration.
        setClickable(true);''')
    # Native lifecycle already disables click during transitions. Gate long click too.
    s = once(s, '''    private void setClickable(boolean val) {
        mToggleTabStackButton.setClickable(val);
    }''', '''    private void setClickable(boolean val) {
        mToggleTabStackButton.setClickable(val);
        if (mToggleTabStackButton.isSandiumDualAction()) {
            mToggleTabStackButton.setLongClickable(val);
        }
    }''')
    return s


def button(s):
    s = once(s, '    private TabSwitcherDrawable mTabSwitcherButtonDrawable;', '''    // SANDIUM_TAB_DUAL_ACTION_V1: keep native count/notification drawable, add small +.
    private boolean mSandiumDualAction;
    private final android.graphics.Paint mSandiumAddPaint =
            new android.graphics.Paint(android.graphics.Paint.ANTI_ALIAS_FLAG);

    boolean isSandiumDualAction() { return mSandiumDualAction; }
    void setSandiumDualAction(boolean enabled) {
        mSandiumDualAction = enabled;
        mSandiumAddPaint.setColor(ThemeUtils.getThemedToolbarIconTint(
                getContext(), BrandedColorScheme.APP_DEFAULT).getDefaultColor());
        invalidate();
    }

    private void drawSandiumAdd(Canvas canvas, float centerX, float centerY) {
        if (!mSandiumDualAction) return;
        float d = getResources().getDisplayMetrics().density;
        // SANDIUM_TAB_BADGE_V2: reference has a blue circular + at top-end,
        // overlapping the existing native count outline, not a detached bottom +.
        float x = centerX + (getLayoutDirection() == LAYOUT_DIRECTION_RTL ? -10 : 10) * d;
        float y = centerY - 10 * d;
        mSandiumAddPaint.setStyle(android.graphics.Paint.Style.FILL);
        mSandiumAddPaint.setColor(android.graphics.Color.rgb(110, 142, 181));
        mSandiumAddPaint.setAlpha(isEnabled() ? 255 : 100);
        canvas.drawCircle(x, y, 6 * d, mSandiumAddPaint);
        mSandiumAddPaint.setColor(android.graphics.Color.rgb(8, 8, 8));
        mSandiumAddPaint.setStrokeWidth(1.5f * d);
        mSandiumAddPaint.setStrokeCap(android.graphics.Paint.Cap.ROUND);
        mSandiumAddPaint.setAlpha(isEnabled() ? 255 : 100);
        canvas.drawLine(x - 3 * d, y, x + 3 * d, y, mSandiumAddPaint);
        canvas.drawLine(x, y - 3 * d, x, y + 3 * d, mSandiumAddPaint);
    }

    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        drawSandiumAdd(canvas, getWidth() / 2f, getHeight() / 2f);
    }

    @Override
    public void onInitializeAccessibilityNodeInfo(android.view.accessibility.AccessibilityNodeInfo info) {
        super.onInitializeAccessibilityNodeInfo(info);
        if (mSandiumDualAction) {
            info.addAction(new android.view.accessibility.AccessibilityNodeInfo.AccessibilityAction(
                    android.view.accessibility.AccessibilityNodeInfo.ACTION_CLICK,
                    getContext().getString(R.string.sandium_toolbar_new_tab)));
            info.addAction(new android.view.accessibility.AccessibilityNodeInfo.AccessibilityAction(
                    android.view.accessibility.AccessibilityNodeInfo.ACTION_LONG_CLICK,
                    getContext().getString(R.string.sandium_toolbar_show_tabs)));
        }
    }

    private TabSwitcherDrawable mTabSwitcherButtonDrawable;''')
    s = once(s, '''        mTabSwitcherButtonDrawable.setNotificationBackground(brandedColorScheme);''', '''        mTabSwitcherButtonDrawable.setNotificationBackground(brandedColorScheme);
        mSandiumAddPaint.setColor(ThemeUtils.getThemedToolbarIconTint(getContext(), brandedColorScheme).getDefaultColor());''')
    s = once(s, '        setContentDescription(drawableText);', '''        if (mSandiumDualAction) {
            drawableText = getContext().getString(R.string.sandium_toolbar_tabs_dual_action, tabCount);
        }
        setContentDescription(drawableText);''')
    s = once(s, '        mTabSwitcherButtonDrawable.draw(canvas);', '''        mTabSwitcherButtonDrawable.draw(canvas);
        drawSandiumAdd(canvas, backgroundWidth / 2f, backgroundHeight / 2f);''')
    return s


def strings(s):
    return once(s, '</resources>', '''    <string name="sandium_toolbar_show_tabs">Show tabs</string>
    <string name="sandium_toolbar_tabs_dual_action">New tab. Touch and hold to show tabs. %1$d open tabs.</string>
</resources>''')


def transformations(src):
    return [(src / bottom.PHONE, phone),
            (src / bottom.BASE / 'java/res/layout/toolbar_phone.xml', layout),
            (src / UTIL, page_info), (src / DIMENS, dimens),
            (src / TOP / 'ToggleTabStackButtonCoordinator.java', coordinator),
            (src / TOP / 'ToggleTabStackButton.java', button),
            (src / bottom.BASE / 'java/res/values/sandium_toolbar.xml', strings)]


def apply(src, verify=False):
    if subprocess.check_output(['git', '-C', str(src), 'rev-parse', 'HEAD'], text=True).strip() != bottom.PIN:
        raise ValueError('Unexpected Chromium pin')
    # Prepare every transformation before writes; reject partial/changed source.
    changes = [(p, f(p.read_text())) for p, f in transformations(src)]
    if verify:
        for p, t in changes:
            if p.read_text() != t: raise ValueError('Missing toolbar refinement: ' + str(p))
    else:
        for p, t in changes: p.write_text(t)


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--src', type=Path, required=True)
    p.add_argument('--verify-only', action='store_true'); a = p.parse_args()
    apply(a.src, a.verify_only)
