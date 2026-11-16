import importlib.util
from pathlib import Path
import unittest
HERE=Path(__file__).parent
spec=importlib.util.spec_from_file_location('patch',HERE/'patch.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
class CandidateTests(unittest.TestCase):
    def test_pinned_page_idempotent_and_disabled(self):
        source=(HERE/'fixtures/BraveNewTabPage.java').read_text();result=p.page(source)
        self.assertEqual(result,p.page(result))
        self.assertIn('EdgeToEdgeUtils.isSandiumNativeStatusEnabled()',result)
        self.assertIn('topInsetProvider.addObserver(mSandiumNativeTopInsetObserver)',result)
        self.assertIn('removeObserver(mSandiumNativeTopInsetObserver)',result)
        self.assertIn('SDK_INT >= 35',result)
        self.assertIn('super.onToEdgeChange(systemTopInset, consumeTopInset, layoutType)',result)
        self.assertNotIn('setTopControlsHeight',result)
    def test_layout_preserves_geometry_and_lifecycle(self):
        source=(HERE.parents[1]/'.circleci/features/news-removal/expected/android/java/org/chromium/chrome/browser/ntp/BraveNewTabPageLayout.java').read_text()
        result=p.layout(source);self.assertEqual(result,p.layout(result))
        for token in ['setPadding(', 'setTranslationY(', 'requestLayout(', 'setLayoutParams(', 'onDetachedFromWindow()', 'onAttachedToWindow()']:
            self.assertEqual(result.count(token),source.count(token),token)
        self.assertIn('super.dispatchDraw(canvas)',result)
        self.assertIn('super.drawChild(canvas, child, drawingTime)',result)
        self.assertIn('canvas.concat(imageView.getImageMatrix())',result)
        self.assertNotIn('image.setBounds(',result)
        self.assertNotIn('canvas.scale(',result)
        self.assertIn('mSandiumNativeStatusInset > 0 ? getHeight()',result)
        self.assertEqual(result.count('new FetchWallpaperWorkerTask('),source.count('new FetchWallpaperWorkerTask('))
        self.assertNotIn('drawRect(',result)
    def test_pinned_native_foreground_owner(self):
        source=(HERE/'fixtures/NewTabPageCoordinator.java').read_text()
        self.assertIn('toolbarHeightNoShadow + mTopInset',source)
        self.assertIn('mTopInset = supportsEdgeToEdgeOnTop ? systemTopInset : 0',source)
    def test_chromium_owner_composition(self):
        root=HERE.parents[1]
        spec=importlib.util.spec_from_file_location('status',root/'.circleci/scripts/apply-sandium-scroll-status-bar.py')
        status=importlib.util.module_from_spec(spec);spec.loader.exec_module(status)
        for name in ['EdgeToEdgeBaseLayout.java','EdgeToEdgeUtils.java','EdgeToEdgeControllerCreator.java','InsetObserver.java','EdgeToEdgeLayoutCoordinator.java',
                     'EdgeToEdgeSystemBarColorHelper.java','EdgeToEdgeControllerImpl.java']:
            src=(root/'.circleci/tests/fixtures/status-bar'/name).read_text()
            base=status.transform(name,src);candidate=p.chromium(name,base)
            self.assertEqual(candidate,p.chromium(name,candidate),name)
            self.assertEqual(base,p.undo_chromium(name,candidate),name)
            self.assertEqual(candidate,p.chromium(name,status.transform(name,
                p.undo_chromium(name,candidate))),name)
            if name=='EdgeToEdgeUtils.java':
                self.assertIn('SANDIUM_NATIVE_STATUS_CANDIDATE = false',candidate)
            if name=='EdgeToEdgeControllerImpl.java':
                self.assertIn('&& EdgeToEdgeUtils.isRegularNtp(tab)) return shouldSandiumNativeStatus(tab);',candidate)
                self.assertEqual(candidate.count('setSandiumNativeStatusProtection(false);'),2)
                self.assertEqual(candidate.count('setTopControlsHeight'),base.count('setTopControlsHeight'))
            if name=='InsetObserver.java':
                self.assertEqual(candidate.count('updateCurrentSafeArea();'),base.count('updateCurrentSafeArea();'))

    def test_api15_reuses_upstream_architecture_without_relaxing_web_gate(self):
        root=HERE.parents[1]
        spec=importlib.util.spec_from_file_location('status',root/'.circleci/scripts/apply-sandium-scroll-status-bar.py')
        status=importlib.util.module_from_spec(spec);spec.loader.exec_module(status)
        source=(root/'.circleci/tests/fixtures/status-bar/EdgeToEdgeUtils.java').read_text()
        result=p.chromium('EdgeToEdgeUtils.java',status.transform('EdgeToEdgeUtils.java',source))
        self.assertIn('Build.VERSION.SDK_INT >= 35',result)
        self.assertIn('SANDIUM_TOP_UNDERLAP_EXPERIMENT && Build.VERSION.SDK_INT >= 36',result)
        self.assertIn('getEverywhereOverrides().isEnabledForManufacturerVersion()',result)
        self.assertIn('if (ChromeFeatureList.sEdgeToEdgeEverywhere.isEnabled()) {',result)
        self.assertNotIn('ChromeFeatureList.sEdgeToEdgeEverywhere.isEnabled()\n',result)
        # With the candidate off, upstream feature routing stays exactly unchanged.
        for sdk in (30,34,35,36):
            for upstream in (False,True):
                self.assertEqual(upstream,upstream or (False and sdk>=35))

    def test_legacy_path_keeps_global_everywhere_and_uses_native_owner(self):
        root=HERE.parents[1]
        spec=importlib.util.spec_from_file_location('status',root/'.circleci/scripts/apply-sandium-scroll-status-bar.py')
        status=importlib.util.module_from_spec(spec);spec.loader.exec_module(status)
        def method(src, signature):
            start=src.index(signature);at=src.index('{',start);depth=1;end=at+1
            while depth:
                depth+=(src[end]=='{')-(src[end]=='}');end+=1
            return src[start:end]
        name='EdgeToEdgeUtils.java'
        src=(root/'.circleci/tests/fixtures/status-bar'/name).read_text()
        base=status.transform(name,src);candidate=p.chromium(name,base)
        signature='public static boolean isEdgeToEdgeEverywhereEnabled()'
        self.assertEqual(method(base,signature),method(candidate,signature))
        name='EdgeToEdgeControllerImpl.java'
        src=(root/'.circleci/tests/fixtures/status-bar'/name).read_text()
        candidate=p.chromium(name,status.transform(name,src))
        self.assertIn('updateSandiumLegacyProtection(active && !mDisablePaddingRootView)',candidate)
        self.assertIn('!(isDrawingToEdge() || mSandiumNativeStatusProtection)',candidate)
        self.assertIn('getOverlay().remove(mSandiumLegacyProtection)',candidate)
        self.assertIn('view.getAlpha() == 0f',candidate)
        self.assertNotIn('setOnTouchListener',candidate)

    def test_settings_api15_opt_in_is_activity_local(self):
        root=HERE.parents[1]
        src=(root/'.circleci/tests/fixtures/motion/BraveSettingsActivity.java').read_text()
        result=p.settings_activity(src)
        self.assertEqual(result,p.settings_activity(result))
        self.assertNotIn('ensureEdgeToEdgeLayoutCoordinator()',result)
        self.assertNotIn('createSystemBarColorHelperSupplier()',result)
        self.assertNotIn('wrapContentWithEdgeToEdgeLayout()',result)
        self.assertIn('addOnPreDrawListener(mSandiumStatusBeforeDraw)',result)
        self.assertIn('removeOnPreDrawListener(mSandiumStatusBeforeDraw)',result)
        self.assertLess(result.index('addOnPreDrawListener('),result.index('super.onCreate(savedInstanceState)'))
        self.assertIn('sandiumUpdateSettingsStatusProtection(rootWindowInsets)',result)
        self.assertIn('getOverlay().remove(mSandiumStatusProtection)',result)
        self.assertIn('super.canColorStatusBarWithEdgeToEdgeHelper()',result)
        self.assertEqual(result.count('setOnApplyWindowInsetsListener'),src.count('setOnApplyWindowInsetsListener'))
        self.assertEqual(result.count('setPadding('),src.count('setPadding('))

    def test_settings_composed_theme_fade_and_bottom_ownership(self):
        root=HERE.parents[1]
        def load(name):
            spec=importlib.util.spec_from_file_location(name,root/'.circleci/scripts'/f'{name}.py')
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
        theme=load('apply-sandium-native-theme');fade=load('apply-sandium-settings-fade')
        source=(root/'.circleci/tests/fixtures/motion/BraveSettingsActivity.java').read_text()
        base=fade.brave(theme.settings_surface(theme.settings_motion(source)))
        candidate=p.settings_activity(base)
        self.assertEqual(candidate,p.settings_activity(candidate))
        self.assertIn('private int sandiumSettingsBackground()',candidate)
        # No second writer for the existing root, recycler, IME or navbar insets.
        for line in base.splitlines():
            if any(token in line for token in ('setBottomPadding(', 'setPadding(', 'getInsets(WindowInsetsCompat.Type.ime()', 'getInsets(WindowInsetsCompat.Type.navigationBars()')):
                self.assertEqual(base.count(line),candidate.count(line),line)
        self.assertNotIn('wrapContentWithEdgeToEdgeLayout()',candidate)
        self.assertIn('!EdgeToEdgeUtils.isEdgeToEdgeEverywhereEnabled()',candidate)

    def test_unknown_source_rejected(self):
        for f in [p.page,p.layout]:
            with self.assertRaises(ValueError):f('other source')
if __name__=='__main__':unittest.main()
