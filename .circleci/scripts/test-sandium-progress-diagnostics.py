import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('progress',Path(__file__).with_name('apply-sandium-progress-diagnostics.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Tests(unittest.TestCase):
    def source(self):return (ROOT/'tests/fixtures/progress/ToolbarProgressBarLayer.java').read_text()
    def test_idempotent(self):
        out=m.transform(self.source());self.assertEqual(out,m.transform(out))
    def test_fail_closed(self):
        with self.assertRaises(ValueError):m.transform('class Changed {}')
    def test_preserve_rendering(self):
        before=self.source();after=m.transform(before)
        for token in ['.offset(0, yOffset)', 'setVisibility(', 'setTranslationY(', 'SetHideLayerAndSubtree', 'setAlpha(']:
            self.assertEqual(before.count(token),after.count(token))
    def test_trace_only_bounded_private(self):
        out=m.transform(self.source())
        self.assertIn('TraceEvent.enabled()',out);self.assertIn('mSandiumProgressTraceCount < 24',out)
        for token in ['getUrl(', 'getText(', 'getTitle(', 'Log.i(', 'postDelayed(']:self.assertNotIn(token,out)
        self.assertIn('mSandiumProgressTraceCount = 0',out)
if __name__=='__main__':unittest.main()
