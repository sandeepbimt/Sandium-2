"""Held combined native source plan. No production activation or runtime claim."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[1]
MENU = ROOT / 'experiments/native-menu'
sys.path.insert(0, str(MENU))
import grid_adapter
spec = importlib.util.spec_from_file_location('combined_toolbar', ROOT/'experiments/native-toolbar/adapter.py')
toolbar = importlib.util.module_from_spec(spec)
spec.loader.exec_module(toolbar)

class NativeUiComposition(unittest.TestCase):
    def test_combined_exact_plans_replay_and_reject_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)
            originals = {}
            for relative in (grid_adapter.adapter.HANDLER, grid_adapter.adapter.BUILD,
                             grid_adapter.APP, grid_adapter.DRAG):
                originals[relative] = (MENU/'fixtures'/Path(relative).name).read_text()
            for relative in (toolbar.PHONE, toolbar.PROGRESS):
                self.assertNotIn(relative, originals)
                originals[relative] = (toolbar.HERE/'fixtures'/Path(relative).name).read_text()
            for relative, text in originals.items():
                target = source/relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text)
            menu = grid_adapter.plan(source)
            paint = toolbar.plan(source)
            self.assertFalse(set(menu) & set(paint))
            combined = {**menu, **paint}
            self.assertEqual(len(combined), 20)
            for target, text in combined.items():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text)
            self.assertEqual(menu, grid_adapter.plan(source))
            self.assertEqual(paint, toolbar.plan(source))
            self.assertEqual(len(grid_adapter.verify_applied(source)), 18)
            for relative, planner in ((grid_adapter.APP, grid_adapter.plan),
                                      (toolbar.PROGRESS, toolbar.plan)):
                target = source/relative
                expected = target.read_text()
                target.write_text(expected+'\n// unreviewed mutation\n')
                with self.assertRaises(ValueError):
                    planner(source)
                target.write_text(expected)
            self.assertEqual(combined, {**grid_adapter.plan(source), **toolbar.plan(source)})

if __name__ == '__main__': unittest.main()
