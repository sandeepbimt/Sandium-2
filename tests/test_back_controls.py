"""Pinned full-source transformation checks; Android runtime is verified by CI/device."""
import hashlib
import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('controls', ROOT / '.circleci/scripts/apply-sandium-back-controls.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class BackControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for relative, _, _ in m.LEGACY_GESTURE_CHANGES + m.CHANGES:
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / 'tests/fixtures/back-controls' / path.name, path)

    def test_application_and_repeated_stage(self):
        first = m.plan(self.root)
        for path, text in first.items():
            path.write_text(text)
        self.assertEqual(first, m.plan(self.root))

    def test_upstream_gesture_flow_preserved(self):
        result = m.plan(self.root)
        for path, new in result.items():
            expected = path.read_text()
            for relative, old, replacement in m.CHANGES:
                if path == self.root / relative:
                    expected = expected.replace(old, replacement)
            self.assertEqual(expected, new)
        toolbar = result[self.root / (m.PREFIX + 'toolbar/ToolbarManager.java')]
        nav = result[self.root / (m.PREFIX + 'gesturenav/NavigationHandler.java')]
        self.assertEqual((toolbar + nav).count('Always force to show the top control'), 2)
        self.assertIn('TabBrowserControlsConstraintsHelper', nav)
        self.assertIn('mHandler.onBackStarted(', toolbar)
        self.assertIn('mTabOnBackGestureHandler.onBackCancelled(false);', nav)
        self.assertIn('mTabOnBackGestureHandler.onBackInvoked(false);', nav)
        self.assertIn('mTabOnBackGestureHandler.onBackStarted(', nav)
        self.assertIn('GestureNavigationUtils.allowTransition(mTab, forward)', nav)
        self.assertIn('TabBrowserControlsConstraintsHelper\n', toolbar)

    def test_corrupt_anchor_fails_without_writes(self):
        path = self.root / m.LEGACY_GESTURE_CHANGES[1][0]
        path.write_text(path.read_text().replace('mTab, BrowserControlsState.SHOWN', 'otherTab, BrowserControlsState.SHOWN'))
        before = {p:p.read_bytes() for p in self.root.rglob('*.java')}
        with self.assertRaises(RuntimeError):
            m.plan(self.root)
        self.assertEqual(before, {p:p.read_bytes() for p in before})

    def test_duplicate_anchor_rejected(self):
        path = self.root / m.LEGACY_GESTURE_CHANGES[0][0]
        path.write_text(path.read_text() + m.LEGACY_GESTURE_CHANGES[0][1])
        with self.assertRaises(RuntimeError):
            m.plan(self.root)

    def test_reused_legacy_tree_restores_exact_original(self):
        originals = {}
        for relative, upstream, legacy in m.LEGACY_GESTURE_CHANGES:
            path = self.root / relative
            originals.setdefault(path, path.read_text())
            path.write_text(path.read_text().replace(upstream, legacy, 1))
        result = m.plan(self.root)
        for path, original in originals.items():
            self.assertEqual(original, result[path])
        for path, text in result.items():
            path.write_text(text)
        self.assertEqual(result, m.plan(self.root))

    def test_reveal_precedes_handler_and_stays_transition_gated(self):
        result = m.plan(self.root)
        for relative, upstream, legacy in m.LEGACY_GESTURE_CHANGES[:2]:
            text = result[self.root / relative]
            pos = text.index(upstream)
            handler = ('mHandler.onBackStarted(' if 'ToolbarManager' in relative
                       else 'mTabOnBackGestureHandler.onBackStarted(')
            self.assertGreater(text.index(handler, pos), pos)
            self.assertIn('/* animate= */ true', upstream)
        nav = result[self.root / m.LEGACY_GESTURE_CHANGES[1][0]]
        self.assertIn('TabOnBackGestureHandler.shouldAnimateNavigationTransition(', nav)

    def test_full_wiring(self):
        spec = importlib.util.spec_from_file_location('wiring', ROOT / '.circleci/scripts/flow_wiring.py')
        wiring = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(wiring)
        wiring.verify_full_wiring(ROOT)

if __name__ == '__main__':
    unittest.main()
