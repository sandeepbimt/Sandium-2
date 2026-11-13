"""Source contract tests. These do NOT replace Android compilation/device tests."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

BASE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('patch', BASE.parent / 'scripts/apply-sandium-scroll-status-bar.py')
patch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patch)

class UnderlapPatchTests(unittest.TestCase):
    def original(self, name):
        return (BASE / 'fixtures/status-bar' / name).read_text()

    def test_all_pinned_sources_transform_idempotently(self):
        for name in patch.FILES:
            with self.subTest(name=name):
                once = patch.transform(name, self.original(name))
                self.assertNotEqual(once, self.original(name))
                self.assertEqual(once, patch.transform(name, once))

    def test_rejects_drift_before_any_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, path in patch.FILES.items():
                dest = root / path
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(self.original(name))
            # Last input fails: earlier prepared changes must not be written.
            last = list(patch.FILES.values())[-1]
            (root / last).write_text('unrecognized pinned source')
            before = {p: (root/p).read_text() for p in patch.FILES.values()}
            with self.assertRaises(RuntimeError): patch.apply(root)
            self.assertEqual(before, {p: (root/p).read_text() for p in patch.FILES.values()})

    def test_disable_reenable_existing_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, path in patch.FILES.items():
                dest = root / path
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(self.original(name))
            patch.apply(root)
            enabled = {p: (root/p).read_text() for p in patch.FILES.values()}
            patch.apply(root, enabled=False)
            self.assertIn('SANDIUM_TOP_UNDERLAP_EXPERIMENT = false;',
                          (root / patch.FILES['EdgeToEdgeUtils.java']).read_text())
            disabled = {p: (root/p).read_text() for p in patch.FILES.values()}
            patch.apply(root, enabled=False)
            self.assertEqual(disabled, {p: (root/p).read_text() for p in patch.FILES.values()})
            patch.apply(root, enabled=True)
            self.assertEqual(enabled, {p: (root/p).read_text() for p in patch.FILES.values()})

    def test_scope_and_no_scroll_threshold(self):
        text = patch.transform('EdgeToEdgeControllerImpl.java', self.original('EdgeToEdgeControllerImpl.java'))
        for gate in ['!mDisablePaddingRootView', 'ChromeTabbedActivity', 'isInMultiWindowMode',
                     'isInPictureInPictureMode', 'smallestScreenWidthDp >= 600',
                     'ORIENTATION_PORTRAIT', 'mSandiumCrashedTab', 'mStatusIndicatorVisible',
                     'getPersistentFullscreenMode()', 'isNativePage()', 'isIncognito()',
                     '!"https".equals(scheme)', '!"http".equals(scheme)',
                     'LayoutType.BROWSING', 'mKeyboardInsets.bottom > 0',
                     'systemInsets.left == 0', 'systemInsets.right == 0',
                     'ControlsPosition.TOP', 'isVisibilityForced()']:
            self.assertIn(gate, text)
        self.assertNotIn('mSandiumSawUserScroll', text)
        self.assertNotIn('getTopControlHiddenRatio()', text)
        self.assertIn('changedWindowState = true;', text)

    def test_separate_protection_and_safe_area(self):
        base = patch.transform('EdgeToEdgeBaseLayout.java', self.original('EdgeToEdgeBaseLayout.java'))
        self.assertLess(base.index('super.dispatchDraw(canvas);'), base.index('canvas.drawRect(0, 0, getWidth()'))
        self.assertIn('android.graphics.LinearGradient', base)
        observer = patch.transform('InsetObserver.java', self.original('InsetObserver.java'))
        self.assertIn('newSafeArea.top = Math.max(newSafeArea.top, mSandiumTopInsetForEdgeToEdge)', observer)
        layout = patch.transform('EdgeToEdgeLayoutCoordinator.java', self.original('EdgeToEdgeLayoutCoordinator.java'))
        self.assertIn('overallInsets.left, overallInsets.top, overallInsets.right, overallInsets.bottom', layout)
        self.assertNotIn('setPadding(0, 0, 0, 0)', layout)

    def test_cutout_and_bypass_guards(self):
        text = patch.transform('EdgeToEdgeControllerImpl.java', self.original('EdgeToEdgeControllerImpl.java'))
        for guard in ['cutoutInsets.left == 0', 'cutoutInsets.right == 0',
                      'cutoutInsets.bottom == 0', 'cutoutInsets.top <= systemInsets.top',
                      'captionInsets.equals(Insets.NONE)', 'public void onUrlUpdated(Tab tab)',
                      'public void onPageLoadFailed(Tab tab, int errorCode)',
                      'clearSandiumUnderlapBeforeInsetsBypass();']:
            self.assertIn(guard, text)
        self.assertIn('if (sandiumUnderlap || wasSandiumUnderlap)', text)
        self.assertIn('observer.onToEdgeChange(mSystemInsets.top, false, layoutType)', text)

    def test_android16_gate_and_color_restoration(self):
        utils = patch.transform('EdgeToEdgeUtils.java', self.original('EdgeToEdgeUtils.java'))
        self.assertIn('SANDIUM_TOP_UNDERLAP_EXPERIMENT && Build.VERSION.SDK_INT >= 36', utils)
        helper = patch.transform('EdgeToEdgeSystemBarColorHelper.java', self.original('EdgeToEdgeSystemBarColorHelper.java'))
        self.assertIn('mSandiumScrollUnderStatusBar ? 0x00000000 : mStatusBarColor', helper)
        self.assertIn('mSandiumRestoringStatusBar = mSandiumScrollUnderStatusBar && !active', helper)
        self.assertIn('mForceLightStatusBarColor || mSandiumScrollUnderStatusBar', helper)

if __name__ == '__main__': unittest.main()
