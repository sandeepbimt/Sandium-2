#!/usr/bin/env python3
"""Source contracts, not Android/device verification."""
import importlib.util
from pathlib import Path
import unittest
HERE=Path(__file__).resolve().parent

def load(n):
    s=importlib.util.spec_from_file_location(n,HERE/(n+'.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
m=load('apply-sandium-focus-follow');u=load('apply-sandium-unified-address')
class FocusFollow(unittest.TestCase):
    def source(self):return u.position((HERE.parent.parent/'tests/fixtures/unified-address/ToolbarPositionController.java').read_text())
    def test_idempotent_and_guarded(self):
        out=m.transform(self.source());self.assertEqual(out,m.transform(out))
        self.assertIn('mBottomToolbarLayer != null && mProgressBarLayer != null',out)
        start=out.index('if (newControlsPosition == mCurrentPosition.get()) {')
        end=out.index('        int newTopHeight;',start)
        block=out[start:end]
        self.assertIn('newControlsPosition == ControlsPosition.BOTTOM',block)
        self.assertEqual(block.count('updateViewOffset('),2)
    def test_no_new_offset_formula_or_global_preference(self):
        before=self.source();out=m.transform(before)
        for x in ['layerYOffset = Math.max(layerYOffset - keyboardHeight, maxTranslation);',
                  'return allowToolbarPositioningInResizeMode && isKeyboardInResizeMode;',
                  '|| doesUserPreferTopToolbar', '|| isFindInPageShowing']:
            self.assertIn(x,out)
        self.assertEqual(before.count('setTranslationY('),out.count('setTranslationY('))
    def test_no_private_trace_values(self):
        source=Path(m.__file__).read_text()
        for x in ['getUrl(', 'getTitle(', 'getText(', 'getSpec(', 'Log.i(', 'postDelayed(']:self.assertNotIn(x,source)
        self.assertEqual(source.count('TraceEvent.enabled()'),2)
    def test_order_required(self):
        with self.assertRaises(ValueError):m.transform('class Unrelated {}')
if __name__=='__main__':unittest.main()
