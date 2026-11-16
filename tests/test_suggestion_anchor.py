import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('anchor',ROOT/'.circleci/scripts/apply-sandium-suggestion-anchor.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class SuggestionAnchor(unittest.TestCase):
    def composed(self):
        out={}
        for rel,old,new in m.CHANGES:
            name=Path(rel).name
            original=out.get(name,(ROOT/'tests/fixtures/suggestion-anchor'/name).read_text())
            out[name]=m.transform(original,old,new)
        return out
    def test_exact_and_idempotent(self):
        out=self.composed()
        for rel,old,new in m.CHANGES:
            self.assertEqual(out[Path(rel).name],m.transform(out[Path(rel).name],old,new))
    def test_native_reverse_no_manual_geometry_or_adapter_reorder(self):
        out=self.composed()['OmniboxSuggestionsDropdown.java']
        self.assertIn('mLayoutScrollListener.setReverseLayout(enabled);',out)
        self.assertNotIn('offsetChildrenVertical',out)
        self.assertNotIn('setStackFromEnd',out)
        self.assertNotIn('Collections.reverse',out)
        self.assertIn('scrollToPositionWithOffset(0, 0)',out)
    def test_scroll_keyboard_direction_and_keyboard_selection(self):
        out=self.composed()['OmniboxSuggestionsDropdown.java']
        self.assertIn('return -updateKeyboardVisibilityAndScroll(-resultingDeltaY, -requestedDeltaY);',out)
        self.assertIn('? KeyNavigationUtil.isGoUp(event) : KeyNavigationUtil.isGoDown(event)',out)
        self.assertIn('? KeyNavigationUtil.isGoDown(event) : KeyNavigationUtil.isGoUp(event)',out)
        self.assertIn('event.isShiftPressed()',out)
        self.assertIn('selectedView.performClick()',out)
    def test_initial_hint_and_changes(self):
        out=self.composed()
        self.assertEqual(out['OmniboxSuggestionsContainer.java'].count('mDropdown.setAnchorSuggestionsToBottom('),3)
    def test_only_phone_bottom_default_false(self):
        out=self.composed()
        self.assertIn('&& mControlsPositionSupplier.get() == ControlsPosition.BOTTOM',out['OmniboxSuggestionsDropdownEmbedderImpl.java'])
        self.assertIn('default boolean shouldAnchorSuggestionsToBottom() { return false; }',out['OmniboxSuggestionsDropdownEmbedder.java'])
    def test_short_dropdown_is_anchored_not_just_reversed(self):
        import xml.etree.ElementTree as ET
        xml=ET.parse(ROOT/'tests/fixtures/suggestion-anchor/suggestions_result_container.xml').getroot()
        ns='{http://schemas.android.com/apk/res/android}'
        self.assertEqual(xml.attrib[ns+'layout_height'],'match_parent')
        self.assertEqual(xml[0].attrib[ns+'layout_height'],'wrap_content')
        out=self.composed()['OmniboxSuggestionsContainer.java']
        self.assertIn('mSandiumOriginalDropdownGravity = ((FrameLayout.LayoutParams)',out)
        self.assertIn('~android.view.Gravity.VERTICAL_GRAVITY_MASK',out)
        self.assertIn('| android.view.Gravity.BOTTOM',out)
        self.assertIn(': mSandiumOriginalDropdownGravity;',out)
        self.assertIn('if (dropdownParams.gravity != targetGravity)',out)
        self.assertNotIn('setTranslationY',out)

    def test_reverse_decorations_and_rounding(self):
        out=self.composed()
        self.assertIn('outRect.bottom = mHeaderHeight',out['HeaderDecoration.java'])
        self.assertIn('child.getBottom() + lp.bottomMargin + mHeaderHeight / 2f',out['HeaderDecoration.java'])
        self.assertIn('outRect.bottom = mSeparatorHeight',out['GroupSeparatorDecoration.java'])
        self.assertIn('+ child.getTranslationY()',out['GroupSeparatorDecoration.java'])
        self.assertIn('? child.getY() + mHeight : child.getY() + child.getHeight()',out['SuggestionHorizontalDivider.java'])
        view=out['BaseSuggestionView.java']
        self.assertIn('mSandiumLogicalRoundTop = top;',view)
        self.assertIn('super.setRoundingEdges(mSandiumReverseRounding ? bottom : top,',view)
        self.assertIn('suggestion.setSandiumReverseRounding(false)',out['OmniboxSuggestionsDropdown.java'])
        self.assertIn('invalidateItemDecorations()',out['OmniboxSuggestionsDropdown.java'])
    def test_repeat_entire_transform_sequence(self):
        out=self.composed();again=dict(out)
        for rel,old,new in m.CHANGES:
            name=Path(rel).name
            again[name]=m.transform(again[name],old,new)
        self.assertEqual(out,again)
    def test_unknown_anchor_fails(self):
        with self.assertRaises(RuntimeError):m.transform('unknown','old','new')
if __name__=='__main__': unittest.main()
