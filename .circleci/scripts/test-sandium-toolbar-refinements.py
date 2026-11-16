#!/usr/bin/env python3
"""Pinned transforms and action/layout contracts, not Android/device execution."""
import importlib.util
from pathlib import Path
import unittest
import tempfile
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'.circleci/scripts'/(name+'.py'))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
m=load('apply-sandium-toolbar-refinements');a=load('apply-sandium-unified-address')
FIX=ROOT/'tests/fixtures/toolbar-refinements';UFIX=ROOT/'tests/fixtures/unified-address'

class Refinements(unittest.TestCase):
    def test_address_height_only_changes_background_inset(self):
        raw=(UFIX/'ToolbarPhone.java').read_text()
        base=a.all_phone(a.bottom.phone(raw))
        out=m.phone(base)
        self.assertEqual(out,m.phone(out))
        # Undo only the intended capsule paint adjustment and old duplicate-plus fix:
        # every other byte of the composed ToolbarPhone must remain unchanged.
        added="""
        // SANDIUM_ADDRESS_HEIGHT_V1: +8dp capsule height, matching Quetta proportions.
        // Focus can still expand farther if native/accessibility dimensions require it.
        int sandiumExtraInset = Math.round(4 * getResources().getDisplayMetrics().density
                * (1 - mUrlFocusChangeFraction));
        verticalInset -= Math.min(Math.max(0, verticalInset), sandiumExtraInset);"""
        restored=out.replace(added,'').replace(
            'sandiumNewTab.setVisibility(GONE); // SANDIUM_TAB_DUAL_ACTION_V1: no duplicate + slot.',
            'sandiumNewTab.setVisibility(sandiumCompactToolbar() ? GONE : VISIBLE);')
        self.assertEqual(base,restored)

    def test_address_height_focus_and_density_bounds(self):
        for density in (1, 1.5, 2, 2.625, 3, 4):
            rnd=lambda x: int(x+0.5)
            margin=rnd(8*density)
            for fraction in (0, .25, .5, .75, 1):
                native=margin-int(8*density*fraction/2)
                actual=native-min(max(0,native),rnd(4*density*(1-fraction)))
                self.assertGreaterEqual(actual,0)
                self.assertLessEqual(actual,native)
                if fraction==0:
                    self.assertEqual(2*(native-actual),2*rnd(4*density))
                if fraction==1:
                    self.assertEqual(actual,native)

    def test_native_negative_focus_insets_are_preserved(self):
        for native in (-8, -1, 0):
            for extra in (0, 1, 4):
                actual=native-min(max(0,native),extra)
                self.assertEqual(native,actual)

    def test_tab_dispatch_and_transition_guard(self):
        out=m.coordinator((FIX/'ToggleTabStackButtonCoordinator.java').read_text())
        self.assertEqual(out,m.coordinator(out))
        self.assertIn('sandiumNewTab.performClick()',out)
        self.assertIn('onClickListener.onClick(v)',out)
        self.assertIn('return true; // Consume release',out)
        self.assertIn('if (!v.isEnabled() || !v.isClickable()) return false;',out)
        self.assertIn('mToggleTabStackButton.setLongClickable(val)',out)
        self.assertIn('mToggleTabStackButton.setOnLongClickListener(onLongClickListener)',out)
        self.assertNotIn('openNewTab(',out)

    def test_native_tab_count_badge_and_accessibility(self):
        out=m.button((FIX/'ToggleTabStackButton.java').read_text())
        self.assertEqual(out,m.button(out))
        for token in ('mTabSwitcherButtonDrawable.updateForTabCount','mTabSwitcherButtonDrawable.setNotificationIconStatus',
                      'ACTION_LONG_CLICK','sandium_toolbar_tabs_dual_action','getDefaultColor()',
                      'drawSandiumAdd(canvas, backgroundWidth / 2f, backgroundHeight / 2f)'):
            self.assertIn(token,out)
        self.assertIn('getLayoutDirection() == LAYOUT_DIRECTION_RTL ? -10 : 10',out)
        self.assertIn('float y = centerY - 10 * d;',out)
        self.assertIn('canvas.drawCircle(x, y, 6 * d, mSandiumAddPaint)',out)
        self.assertIn('Color.rgb(25, 140, 255)',out)
        self.assertNotIn('centerY + 8 * d',out)

    def test_no_duplicate_new_tab_slot_even_compact(self):
        raw=(UFIX/'ToolbarPhone.java').read_text();out=m.phone(a.all_phone(a.bottom.phone(raw)))
        self.assertEqual(out,m.phone(out))
        self.assertIn('sandiumNewTab.setVisibility(GONE)',out)
        self.assertNotIn('sandiumNewTab.setVisibility(sandiumCompactToolbar()',out)
        self.assertIn('updateSandiumLeadingShield()',out)
        raw=(UFIX/'toolbar_phone.xml').read_text()
        anchor='        <ViewStub\n            android:id="@+id/optional_button_stub"'
        raw=raw.replace(anchor,'        <include layout="@layout/brave_toolbar" android:layout_width="wrap_content" android:layout_height="48dp" />\n'+anchor)
        out=m.layout(a.layout(a.bottom.layout(raw)))
        self.assertEqual(out,m.layout(out));root=ET.fromstring(out)
        android='{http://schemas.android.com/apk/res/android}'
        plus=next(node for node in root.iter() if node.get(android+'id')=='@+id/sandium_new_tab')
        self.assertEqual(plus.get(android+'visibility'),'gone')
        self.assertEqual(plus.get(android+'importantForAccessibility'),'noHideDescendants')

    def test_native_page_info_relocation_not_warning_deletion(self):
        raw=(FIX/'BrowserUiUtils.java').read_text();out=m.page_info(raw)
        self.assertEqual(out,m.page_info(out))
        self.assertIn('return !DeviceFormFactor.isNonMultiDisplayContextOnTablet(context);',out)
        status=(FIX/'StatusMediator.java').read_text()
        self.assertIn('mPageSecurityLevel == ConnectionSecurityLevel.SECURE',status)
        self.assertIn('&& (isPageInfoMovedToAppMenu() || !mShowStatusIconForSecureOrigins)',status)
        self.assertIn('iconRes = mSecurityIconRes;',status)
        self.assertIn('mPermissionStatusHandler.isClapperQuietIconShowing()',status)

    def test_font_only_exact_ten_percent(self):
        raw=(FIX/'dimens.xml').read_text();out=m.dimens(raw)
        self.assertEqual(out,m.dimens(out))
        before=ET.fromstring(raw);after=ET.fromstring(out)
        changed=[(x.get('name'),x.text,y.text) for x,y in zip(before,after) if x.text!=y.text]
        self.assertEqual(changed,[('location_bar_url_text_size','16sp','14.4sp')])

    def test_menu_labels_and_compact_accessible_indicators(self):
        source=(ROOT/'android/java/org/chromium/chrome/browser/ui/appmenu/SandiumPagedMenu.java').read_text()
        self.assertIn('if (mAllMenu)',source) # Latest user moves Edit into All menu.
        self.assertNotIn('button("+", s(R.string.sandium_menu_edit_description)',source)
        self.assertIn('button(s(R.string.sandium_menu_edit)',source)
        self.assertNotIn('weighted(heading, new View(getContext()));',source)
        self.assertIn('new LinearLayout.LayoutParams(0, 1, 1)',source)
        self.assertIn('editAction.setMinWidth(dp(64))', source)
        self.assertIn('editParams = new LinearLayout.LayoutParams(dp(64), dp(48))', source)
        self.assertNotIn('editParams.setMarginEnd(dp(8))', source)
        self.assertIn('new LinearLayout.LayoutParams(dp(28), dp(48))',source)
        self.assertIn('new FrameLayout.LayoutParams(dp(20), dp(3), Gravity.CENTER)',source)
        self.assertNotIn('if (pages == 2)',source)
        self.assertIn('pager.setContentDescription',source)
        self.assertIn('pager.setMinimumWidth(dp(48))',source)
        self.assertIn('AccessibilityNodeInfo.ACTION_SCROLL_FORWARD',source)
        self.assertIn('AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD',source)
        self.assertIn('showNative(',source) # specialized native actions remain.
        self.assertIn('if (mUncataloguedNativeRow >= 0)', source)
        self.assertIn('() -> showNative(mUncataloguedNativeRow)', source)
        self.assertIn('mUncataloguedNativeRow = -1;', source)
        strings=(ROOT/'android/java/res/values/sandium_menu_strings.xml').read_text()
        self.assertNotIn('>All Menu<',strings);self.assertNotIn('>Edit Menu<',strings)
        self.assertIn('>Edit<',strings)

    def test_grouped_menu_surfaces_preserve_body_and_actions(self):
        source=(ROOT/'android/java/org/chromium/chrome/browser/ui/appmenu/SandiumPagedMenu.java').read_text()
        for token in ('LinearLayout libraryGroup = group(body)',
                      'LinearLayout actionsGroup = group(body)',
                      'LinearLayout availableGroup = group(body)',
                      'grid(libraryGroup, libraryKeys, false)',
                      'actionsGroup.addView(viewport)', 'actionsGroup.addView(pagerScroll)',
                      'LinearLayout availableGrid = column()',
                      'availableGrid.setMinimumHeight(EDITOR_AVAILABLE_ROWS * tileHeight())',
                      'grid(availableGrid, mDraft.hiddenKeys(editableKeys()), true)',
                      'availableGroup.addView(availableGrid)',
                      'group.setBackground(shape(mGroupColor, 12))'):
            self.assertIn(token, source)
        for folder,expected in [('values','#FFFFFF'),('values-night','#1A1A1A')]:
            colors={e.get('name'): e.text for e in ET.parse(ROOT/f'android/java/res/{folder}/sandium_menu_colors.xml').getroot()}
            self.assertEqual(colors['sandium_menu_group_surface'], expected)

    def test_fail_closed(self):
        for f in (m.phone,m.layout,m.page_info,m.dimens,m.coordinator,m.button,m.strings):
            with self.subTest(transform=f.__name__):
                with self.assertRaises(ValueError):f('unrecognized source')

if __name__=='__main__':unittest.main()
