#!/usr/bin/env python3
"""Pinned source-contract tests, NOT Android compilation or device verification."""
import importlib.util
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('unified', HERE/'apply-sandium-unified-address.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
FIX = HERE.parent.parent/'tests/fixtures/unified-address'

class UnifiedAddress(unittest.TestCase):
    def test_native_identity_and_full_editing_are_separate(self):
        original=(FIX/'LocationBarModel.java').read_text()
        out=m.model(original)
        self.assertEqual(out,m.model(out))
        self.assertIn('formatUrlForDisplayOmitSchemePathAndTrivialSubdomains(gurl)',out)
        self.assertIn('buildUrlBarData(gurl, false, identity, formattedUrl)',out)
        self.assertNotIn('split(".")',out)
        # Special/offline/publisher/frozen handling before normal display is intact.
        anchor='            String urlForDisplay = getUrlForDisplay();\n            if (!urlForDisplay.equals(formattedUrl))'
        self.assertEqual(original[:original.index(anchor)],out[:out.index('            String urlForDisplay = getUrlForDisplay();\n            // SANDIUM_CONCISE_NATIVE_DISPLAY_V2')])
        self.assertIn('!urlForDisplay.equals(sandiumNativeDisplay)',out)
        self.assertIn('formatUrlForDisplayOmitSchemeOmitTrivialSubdomains(gurl.getSpec())',out)
        self.assertLess(out.index('SANDIUM_CONCISE_NATIVE_DISPLAY_V2'),out.index('String identity ='))

    def test_v1_display_overlay_upgrades_idempotently(self):
        original=(FIX/'LocationBarModel.java').read_text()
        v2=m.model(original)
        new_start=v2.index('            String urlForDisplay = getUrlForDisplay();\n            // SANDIUM_CONCISE_NATIVE_DISPLAY_V2')
        new_end=v2.index('\n\n            // SANDIUM_UNIFIED_ADDRESS_V1:',new_start)
        old_start=original.index('            String urlForDisplay = getUrlForDisplay();\n            if (!urlForDisplay.equals(formattedUrl))')
        old_end=original.index('\n\n            return buildUrlBarData(gurl, false, formattedUrl);',old_start)
        v1=v2[:new_start]+original[old_start:old_end]+v2[new_end:]
        self.assertEqual(v2,m.model(v1))

    def test_display_admission_contract_cases(self):
        # Decision model only: native formatter output is an explicit input, not
        # reimplemented in Python. Native formatting requires Android testing.
        def admitted(scheme, display, editing, native):
            ordinary=scheme in ('http','https')
            return display==editing or (ordinary and display==native)
        self.assertTrue(admitted('https','google.com/search?q=news',
                                 'https://www.google.com/search?q=news','google.com/search?q=news'))
        self.assertFalse(admitted('https','publisher.example/story',
                                  'https://proxy.example/story','proxy.example/story'))
        self.assertFalse(admitted('chrome','google.com','chrome://ai','google.com'))
        self.assertFalse(admitted('https','login.example.com',
                                  'https://evil.example/path','evil.example/path'))

    def test_native_centering_and_safe_overflow(self):
        out=m.location_phone((FIX/'LocationBarPhone.java').read_text())
        self.assertEqual(out,m.location_phone(out))
        self.assertIn('mUrlBar == null || mUrlBar.hasFocus()',out)
        self.assertIn('OmniboxViewUtil.isRegularTabContext(pageClassification)',out)
        self.assertIn('fitsInCenteringSpace',out)
        self.assertIn('ConstraintLayout.LayoutParams.CHAIN_PACKED',out)
        # #1171 device regression: parent centering must not fight UrlBar's
        # native layout/scroll/focus invariant. Do not hide/disable its assertion.
        for forbidden in ('mUrlBar.setHorizontallyScrolling(', 'mUrlBar.setGravity(',
                          'mUrlBar.setTextAlignment(', 'mUrlBar.scrollTo('):
            self.assertNotIn(forbidden,out)
        self.assertIn('SANDIUM_URLBAR_LAYOUT_OWNERSHIP_V1',out)
        self.assertIn('maxUrlWidth = Math.max(1, maxUrlWidth)',out)
        self.assertIn('mLocationBarDataProvider.removeObserver(mUrlObserver)',out)

    def test_centered_url_does_not_add_an_inner_pill(self):
        original=(FIX/'LocationBarPhone.java').read_text()
        out=m.location_phone(original)
        # The single enclosing native toolbar surface remains the paint owner.
        # Centering changes geometry, not URL paint or a second drawable surface.
        for token in ('setBackground(', 'setBackgroundColor(', 'setBackgroundResource(',
                      'GradientDrawable', 'drawRoundRect('):
            self.assertEqual(out.count(token), original.count(token))
        self.assertIn('ConstraintLayout.LayoutParams.CHAIN_PACKED',out)
        self.assertIn('maxUrlWidth = Math.max(1, maxUrlWidth)',out)

    def test_existing_v1_overlay_gets_scroll_ownership_upgrade(self):
        # Re-applying to a checkpoint containing V1 must not bypass the new fix.
        old='// SANDIUM_UNIFIED_ADDRESS_V1\n'+(FIX/'LocationBarPhone.java').read_text()
        out=m.location_phone(old)
        self.assertIn('SANDIUM_URLBAR_LAYOUT_OWNERSHIP_V1',out)
        self.assertNotIn('mUrlBar.setHorizontallyScrolling(',out)
        self.assertEqual(out,m.location_phone(out))

    def test_phone_composition_and_responsive_actions(self):
        out=m.bottom.phone((FIX/'ToolbarPhone.java').read_text())
        for transform in (m.phone,m.phone_leading_shield,m.phone_shield_state,m.responsive):
            out=transform(out)
            self.assertEqual(out,transform(out))
        self.assertIn('widthDp < 360',out)
        self.assertIn('fontScale > 1.3f',out)
        self.assertIn('boolean hideHomeButton = false;',out)
        self.assertIn('sandiumLeading.setAlpha(sandiumRest)',out)
        self.assertNotIn('web && !urlHasFocus()',out)
        self.assertIn('updateSandiumLeadingShield();',out)
        self.assertIn('tabController.forward()',out)
        measure=out[out.index('    protected void onMeasure('):]
        self.assertLess(measure.index('if (mDestroyChecker.isDestroyed())'),measure.index('mSandiumToolbarWidthPx ='))
        draw=out[out.index('    void drawWithoutBackground('):out.index('    protected boolean drawChild(')]
        self.assertLess(draw.index('drawLocationBar(canvas'),draw.index('drawChild(canvas, mHomeButton'))
        self.assertLess(draw.index('drawLocationBar(canvas'),draw.index('drawChild(canvas, sandiumShield'))
        self.assertEqual(draw.count('drawChild(canvas, mHomeButton'),1)
        self.assertIn('urlHasFocus() || sandiumRest == 0f',out)
        self.assertIn('? (urlHasFocus() ? INVISIBLE : VISIBLE) : GONE',out)
        self.assertNotIn('web && !isInTabSwitcherMode() ? VISIBLE : GONE',out)

    def test_shield_hierarchy_after_background(self):
        source=(FIX/'toolbar_phone.xml').read_text()
        anchor='        <ViewStub\n            android:id="@+id/optional_button_stub"'
        source=source.replace(anchor,'        <include layout="@layout/brave_toolbar" android:layout_width="wrap_content" android:layout_height="48dp" />\n'+anchor)
        out=m.layout(m.bottom.layout(source))
        self.assertEqual(out,m.layout(out))
        root=ET.fromstring(out)
        a='{http://schemas.android.com/apk/res/android}'
        ids=[n.get(a+'id') for n in root]
        self.assertLess(ids.index('@+id/location_bar_background_view'),ids.index('@+id/sandium_shields_row'))
        self.assertLess(ids.index('@+id/location_bar'),ids.index('@+id/home_button'))
        self.assertLess(ids.index('@+id/location_bar'),ids.index('@+id/sandium_shields_row'))
        self.assertEqual(out.count('@layout/brave_toolbar'),1)
        self.assertEqual(out.count('@+id/sandium_new_tab'),1)

    def test_focused_bottom_retains_native_keyboard_safety(self):
        before=(FIX/'ToolbarPositionController.java').read_text()
        out=m.position(before)
        self.assertEqual(out,m.position(out))
        self.assertIn('if ((ntpShowing && !isOmniboxFocused)',out)
        self.assertNotIn('|| isOmniboxFocused\n                || isFindInPageShowing',out)
        for invariant in ('|| doesUserPreferTopToolbar', '|| tabSwitcherShowing',
                          '|| isFindInPageShowing', 'shouldIgnoreKeyboardHeightInResizeMode()',
                          'WindowInsetsCompat.Type.ime()', 'mControlContainer.setMaxHeight(maxHeight)'):
            self.assertIn(invariant,out)
        start=before.index('        if (mIsOmniboxFocusedSupplier.get() && mCurrentPosition.get() == ControlsPosition.BOTTOM)')
        self.assertIn(before[start:],out)

    def test_vertical_dots_vector(self):
        root=ET.fromstring(m.menu_resource())
        self.assertEqual(root.tag,'vector')
        self.assertEqual(len(root),1)
        self.assertIn('M12,16',m.menu_resource())

    def test_no_native_replacement_or_network(self):
        source=(HERE/'apply-sandium-unified-address.py').read_text()
        for bad in ('new EditText(', 'ClipboardManager', 'getPrimaryClip(', 'evaluateJavaScript('):
            self.assertNotIn(bad,source)

if __name__=='__main__': unittest.main()
