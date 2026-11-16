"""Source contract tests. These do NOT replace Android compilation/device tests."""
import importlib.util
from pathlib import Path
import tempfile
import hashlib
import json
import types
import unittest

BASE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('patch', BASE.parent / 'scripts/apply-sandium-scroll-status-bar.py')
patch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patch)

def baseline(name):
    folder = BASE / 'fixtures/status-bar/baselines'
    provenance = json.loads((folder / 'provenance.json').read_text())[name]
    data = (folder / (name + '.py')).read_bytes()
    if hashlib.sha256(data).hexdigest() != provenance['sha256']:
        raise ValueError('Historical fixture digest mismatch: ' + name)
    return data.decode()

class UnderlapPatchTests(unittest.TestCase):
    def test_native_settings_gradient_is_paint_only_and_restorable(self):
        name = 'EdgeToEdgeBaseLayout.java'
        original = self.original(name)
        result = patch.transform(name, original)
        native = patch.NATIVE_SETTINGS_PROTECTION
        for token in ['setPadding(', 'requestLayout(', 'setTranslationY(', 'setTopControlsHeight(']:
            self.assertNotIn(token, native)
        self.assertIn('mStatusBarRect.isEmpty()', native)
        self.assertIn('mSandiumTopProtectionHeight == 0', native)
        self.assertIn('BraveSettingsActivity', native)
        self.assertIn('!org.chromium.base.DeviceInfo.isAutomotive()', native)
        self.assertIn('!org.chromium.ui.base.DeviceFormFactor.isNonMultiDisplayContextOnTablet(context)', native)
        self.assertIn('canvas.restoreToCount(saved)', native)
        self.assertIn('0x00000000', native)
        self.assertEqual(result, patch.transform(name, result))
        self.assertEqual(result, patch.apply_native_settings(name,
                         patch.undo_native_settings(name, result)))

    def test_native_forced_light_icons_survive_delegate(self):
        helper = patch.transform('EdgeToEdgeSystemBarColorHelper.java',
                                 self.original('EdgeToEdgeSystemBarColorHelper.java'))
        coordinator = patch.transform('EdgeToEdgeLayoutCoordinator.java',
                                      self.original('EdgeToEdgeLayoutCoordinator.java'))
        self.assertIn('delegateHelper.setStatusBarColor(effectiveColor, true);', helper)
        self.assertIn('updateStatusBarWithLightIconColor(mView.getRootView());', coordinator)
        # Normal native and web callers retain their existing nonforced colour path.
        self.assertIn('delegateHelper.setStatusBarColor(effectiveColor);', helper)
        self.assertIn('updateStatusBarIconColor(mView.getRootView(), mStatusBarColor);', coordinator)

    def test_settings_contrast_is_derived_from_real_paint_owner(self):
        interface = patch.transform('SystemBarColorHelper.java', self.original('SystemBarColorHelper.java'))
        self.assertIn('default boolean hasSandiumStatusProtection() { return false; }', interface)
        helper = patch.transform('EdgeToEdgeSystemBarColorHelper.java', self.original('EdgeToEdgeSystemBarColorHelper.java'))
        self.assertIn('delegateHelper != null && delegateHelper.hasSandiumStatusProtection()', helper)
        coordinator = patch.transform('EdgeToEdgeLayoutCoordinator.java', self.original('EdgeToEdgeLayoutCoordinator.java'))
        self.assertIn('return mView != null && mView.hasSandiumStatusProtection()', coordinator)
        self.assertIn('applyStatusBarColor(); // Protection/contrast follows the actual visible inset.', coordinator)
        self.assertIn('mStatusBarInsets.top > 0', patch.NATIVE_SETTINGS_PROTECTION)
        theme = (BASE.parent/'scripts/apply-sandium-native-theme.py').read_text()
        self.assertNotIn('forceLightIconColor= */ true', theme)

    def original(self, name):
        return (BASE / 'fixtures/status-bar' / name).read_text()

    def test_hidden_gesture_controller_creation_preserves_positive_evidence(self):
        name = 'EdgeToEdgeControllerCreator.java'
        text = patch.transform(name, self.original(name))
        self.assertIn('&& EdgeToEdgeUtils.doAllInsetsIndicateGestureNavigation(insets)', text)
        self.assertIn('&& (!navigationBarInsets.equals(Insets.NONE)', text)
        self.assertIn('|| canCreateSandiumHiddenGestureController(activity, insets)', text)
        for guard in ['isSandiumTopUnderlapExperimentEnabled()', 'isEdgeToEdgeEverywhereEnabled()',
                      'ChromeTabbedActivity', 'isInMultiWindowMode()', 'isInPictureInPictureMode()',
                      'smallestScreenWidthDp >= 600', 'ORIENTATION_PORTRAIT',
                      'doAllInsetsIndicateGestureNavigation(insets)',
                      'isVisible(WindowInsetsCompat.Type.statusBars())',
                      'cutout.top <= status.top', 'Type.captionBar()']:
            self.assertIn(guard, text)
        self.assertEqual(text, patch.transform(name, text))
        self.assertIn('hasInsetsConsumer(InsetConsumerSource.EDGE_TO_EDGE_CONTROLLER_IMPL)', text)
        self.assertIn('mInsetObserver.removeInsetsConsumer(mWindowInsetsConsumer)', text)

    def test_hidden_hint_does_not_relax_downstream_underlap_or_invent_bottom_inset(self):
        before = baseline('57dca6b')
        old = types.ModuleType('old_status'); exec(before, old.__dict__)
        for name in old.FILES:
            self.assertEqual(old.transform(name, self.original(name)),
                             patch.undo_native_settings(name, patch.undo_spacer(name, patch.undo_stable_viewport(name, patch.transform(name, self.original(name))))), name)
        creator = patch.transform('EdgeToEdgeControllerCreator.java',
                                  self.original('EdgeToEdgeControllerCreator.java'))
        self.assertNotIn('setInsets(', creator)
        self.assertNotIn('setDecorFitsSystemWindows', creator)
        self.assertNotIn('getUrl(', creator)
        self.assertNotIn('getTitle(', creator)

    def test_spacer_uses_native_sizing_not_scroll_padding_or_dom(self):
        text = patch.transform('EdgeToEdgeControllerImpl.java',
                               self.original('EdgeToEdgeControllerImpl.java'))
        self.assertIn('controls.getTopControlsHeight() == spacer', text)
        self.assertIn('controls.getTopControlsMinHeight() <= spacer', text)
        self.assertIn('wasSandiumUnderlap || mCurrentTab != null', text)
        for forbidden in ['evaluateJavaScript', 'setTranslationY(', 'getScrollY(', 'scrollTo(', 'setTopControlsHeight(']:
            self.assertNotIn(forbidden, text)
        old = types.ModuleType('previous_status')
        exec(baseline('9ba8861'), old.__dict__)
        self.assertEqual(old.transform('EdgeToEdgeControllerImpl.java',
                                       self.original('EdgeToEdgeControllerImpl.java')),
                         patch.undo_spacer('EdgeToEdgeControllerImpl.java', patch.undo_stable_viewport('EdgeToEdgeControllerImpl.java', text)))

    def test_transitive_provider_forwards_explicit_web_activation(self):
        name = 'TransitiveTopInsetProvider.java'
        text = patch.transform(name, self.original(name))
        self.assertIn('return provider != null && provider.isSandiumWebUnderlapActive();', text)
        self.assertEqual(patch.undo_spacer(name, text), self.original(name))

    def test_stacker_owns_spacer_and_reports_before_height_callbacks(self):
        name = 'TopControlsStacker.java'
        text = patch.transform(name, self.original(name))
        self.assertIn('mControls.put(TopControlType.SANDIUM_STATUS_SPACER, new TopControlLayer()', text)
        self.assertIn('if (mSandiumDestroyed) return;', text)
        start = text.index('private void updateTopControlsHeight(')
        self.assertLess(text.index('setSandiumStatusSpacerHeight(', start),
                        text.index('setTopControlsHeight(', start))
        self.assertIn('mSandiumDestroyed = true;', text)
        self.assertIn('mBrowserControlsSizer.setSandiumStatusSpacerHeight(0);', text)
        tpc = patch.transform('ToolbarPositionController.java', self.original('ToolbarPositionController.java'))
        self.assertIn('mTopInsetProvider.isSandiumWebUnderlapActive()', tpc)
        self.assertIn('sandiumSpacer ? systemTopInset : 0', tpc)
        self.assertIn('public void destroy() {\n        mTopControlsStacker.setSandiumStatusSpacerHeight(0);', tpc)

    def test_fade_stays_inside_reserved_status_strip(self):
        text = patch.transform('EdgeToEdgeBaseLayout.java', self.original('EdgeToEdgeBaseLayout.java'))
        self.assertNotIn('height * 1.5f', text)
        self.assertNotIn('mSandiumTopProtectionHeight * 1.5f', text)
        self.assertIn('new android.graphics.LinearGradient(0, 0, 0, height,', text)
        controller = patch.transform('EdgeToEdgeControllerImpl.java', self.original('EdgeToEdgeControllerImpl.java'))
        self.assertNotIn('setTopControlsHeight(', controller)

    def test_bottom_toolbar_does_not_receive_status_padding(self):
        name = 'ToolbarPositionController.java'
        text = patch.transform(name, self.original(name))
        self.assertIn('getControlsPosition() == ControlsPosition.BOTTOM) {\n            consumeTopInset = false;', text)
        self.assertLess(text.index('consumeTopInset = false;'),
                        text.index('mTopInset = consumeTopInset ? systemTopInset : 0;'))
        self.assertEqual(patch.undo_spacer(name, text), self.original(name))

    def test_all_pinned_sources_transform_idempotently(self):
        for name in patch.FILES:
            with self.subTest(name=name):
                once = patch.transform(name, self.original(name))
                self.assertNotEqual(once, self.original(name))
                self.assertEqual(once, patch.transform(name, once))

    def test_previous_gradient_checkpoint_migrates(self):
        name = "EdgeToEdgeBaseLayout.java"
        current = patch.transform(name, self.original(name))
        previous = patch.undo_native_settings(name, current).replace("0xE6000000", "0xB3000000")
        self.assertEqual(current, patch.transform(name, previous))

    def test_bottom_controls_and_previous_checkpoint_migration(self):
        previous = types.ModuleType('previous')
        # Published navigation baseline replaces unavailable local-only4b4aa9d.
        old_script = baseline('d6b31ba')
        exec(old_script, previous.__dict__)
        for name in patch.FILES:
            old = previous.transform(name, self.original(name))
            current = patch.transform(name, old)
            self.assertEqual(current, patch.transform(name, current), name)
            self.assertEqual(current, patch.transform(name, self.original(name)), name)
        controller = patch.transform('EdgeToEdgeControllerImpl.java', self.original('EdgeToEdgeControllerImpl.java'))
        self.assertIn('ControlsPosition.BOTTOM', controller)
        self.assertIn('controls.getTopControlsHeight() == spacer', controller)
        self.assertIn('controls.getBottomControlsHeight() > 0', controller)
        self.assertIn('public void onTopControlsHeightChanged(int topControlsHeight, int topControlsMinHeight) {\n        refreshSandiumUnderlap();', controller)
        self.assertIn('mBottomControlsHeight = bottomControlsHeight;\n        refreshSandiumUnderlap();', controller)

    def test_current_checkpoint_upgrade_and_back_trace_composition(self):
        old = types.ModuleType('old')
        exec(baseline('d6b31ba'), old.__dict__)
        for name in patch.FILES:
            self.assertEqual(patch.transform(name, self.original(name)),
                             patch.transform(name, old.transform(name, self.original(name))))
        spec = importlib.util.spec_from_file_location('geometry', BASE.parent / 'scripts/trace-sandium-back-geometry.py')
        geom = importlib.util.module_from_spec(spec); spec.loader.exec_module(geom)
        name = 'EdgeToEdgeControllerImpl.java'
        current = patch.transform(name, self.original(name))
        traced = geom.transform(current)
        self.assertEqual(traced, geom.transform(patch.transform(name, geom.reset(traced))))

    def test_unknown_extension_drift_fails_closed(self):
        name = 'EdgeToEdgeControllerImpl.java'
        current = patch.transform(name, self.original(name))
        with self.assertRaisesRegex(RuntimeError, 'Unrecognized status eligibility extension'):
            patch.transform(name, current.replace('SandiumStatusEligibility', 'UnexpectedStatusTrace'))

    def test_visibility_recheck_keeps_guards_and_traces_no_browsing_data(self):
        text = patch.transform('EdgeToEdgeControllerImpl.java', self.original('EdgeToEdgeControllerImpl.java'))
        self.assertIn('public void onAndroidControlsVisibilityChanged(int visibility)', text)
        self.assertIn('public void onOffsetTagsInfoChanged(', text)
        self.assertIn('&& !controls.isVisibilityForced()', text)
        trace = text[text.index('    private void traceSandiumStatusEligibility'):text.index('    private void refreshSandiumUnderlap')]
        self.assertIn('if (!org.chromium.base.TraceEvent.enabled()) return;', trace)
        for private_data in ['getUrl(', 'getTitle(', 'getLastCommittedUrl(', 'evaluateJavaScript']:
            self.assertNotIn(private_data, trace)
        layout = patch.transform('EdgeToEdgeLayoutCoordinator.java', self.original('EdgeToEdgeLayoutCoordinator.java'))
        self.assertIn('SandiumStatusPaintGeometry', layout)
        self.assertIn('protection=', layout)
        self.assertIn('padding=', layout)

    def test_bottom_menu_lock_never_reowns_window_insets(self):
        name = 'EdgeToEdgeControllerImpl.java'
        text = patch.transform(name, self.original(name))
        method = text[text.index('static boolean isSandiumPageAndControlsSupported'):
                      text.index('private boolean shouldSandiumUnderlap')]
        bottom = method[method.index('int spacer ='):]
        self.assertNotIn('isVisibilityForced', bottom)
        self.assertIn('getTopControlsHeight() == spacer', bottom)
        self.assertIn('getTopControlsMinHeight() <= spacer', bottom)
        self.assertIn('getTopControlsMinHeightOffset() <= spacer', bottom)
        self.assertIn('getBottomControlsHeight() > 0', bottom)
        # Authored native test exercises true/false lock cycles, extra layers and keyboard restore.
        native = patch.transform('EdgeToEdgeControllerTest.java', self.original('EdgeToEdgeControllerTest.java'))
        self.assertIn('new boolean[] {true, false, true, false}', native)
        self.assertIn('thenReturn(TOP_INSET + 1)', native)
        self.assertIn('SYSTEM_BARS_WINDOW_INSETS_WITH_KEYBOARD', native)

    def test_header_safe_checkpoint_migration(self):
        previous = types.ModuleType('previous_header')
        exec(baseline('header_safe_1209'), previous.__dict__)
        for name in patch.FILES:
            with self.subTest(name=name):
                old = previous.transform(name, self.original(name))
                current = patch.transform(name, old)
                self.assertEqual(current, patch.transform(name, self.original(name)))
                self.assertEqual(current, patch.transform(name, current))
                self.assertEqual(old, patch.undo_native_settings(name, patch.undo_stable_viewport(name, current)))

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
