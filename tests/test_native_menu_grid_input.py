"""Exact-source hook invariants; these do not execute real Android input dispatch."""
from pathlib import Path
import importlib.util
import unittest
ROOT = Path(__file__).resolve().parents[1]
class GridInputTest(unittest.TestCase):
    def test_typed_root_collection_preserves_native_input(self):
        path=ROOT/'experiments/native-menu/grid_input_adapter.py'
        spec=importlib.util.spec_from_file_location('grid_input_adapter',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        original=module.FIXTURE.read_text();patched=module.transform(original)
        self.assertEqual(module.transform(patched),patched)
        self.assertEqual(patched.replace(module.INSERT,module.ANCHOR),original)
        with self.assertRaises(ValueError):module.transform(original+'\n// changed')
        self.assertIn('rawSVisibleTileTargets());\n                continue;',patched)
        # The hook cannot rewrite native cancellation, coordinates, entrance gating or lifecycle.
        self.assertEqual(original.split('    private boolean menuItemAction(')[0],
                         patched.split('    private boolean menuItemAction(')[0])
        self.assertEqual(original.split('    Rect getScreenVisibleRect(')[1],
                         patched.split('    Rect getScreenVisibleRect(')[1])
    def test_grid_does_not_create_window_or_browser_command(self):
        text=(ROOT/'sandium/menu/java/org/chromium/chrome/browser/ui/appmenu/RawSMenuGridView.java').read_text()
        for forbidden in ('new PopupWindow', 'startActivity(', '.loadUrl(', 'onOptionsItemSelected('):
            self.assertNotIn(forbidden,text)
        self.assertIn('pager.activate(tile, dispatcher)',text)
        self.assertIn('event.getPointerCount() != 1',text)
        self.assertIn('blocked = true',text)
