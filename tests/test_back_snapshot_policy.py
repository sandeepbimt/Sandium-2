"""Pinned-source regressions; Android runtime validation remains required."""
import importlib.util
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('back_policy', ROOT/'.circleci/scripts/apply-sandium-back-transition.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
FIXTURES = ROOT/'tests/fixtures/back-transition'

class BackSnapshotPolicy(unittest.TestCase):
    def setUp(self):
        self.outputs = {str(p.relative_to(FIXTURES)): s for p, s in m.plan(FIXTURES).items()}

    def source(self, suffix):
        return next(s for p, s in self.outputs.items() if p.endswith(suffix))

    def test_native_capture_before_renderer_surface_guard(self):
        s = self.source('navigation_transition_utils.cc')
        start = s.index('CaptureNavigationEntryScreenshotForCrossDocumentNavigations(')
        s = s[start:s.index('// The browser is guaranteed', start)]
        self.assertLess(s.index('GetWindowAndroid()->GetCompositor()'), s.index('bool copied_via_delegate;'))
        self.assertLess(s.index('.increment_copy_output_request_sequence()'), s.index('bool copied_via_delegate;'))
        self.assertLess(s.index('MaybeCopyContentAreaAsHardwareBuffer('), s.index('IsSurfaceAvailableForCopy()'))
        self.assertLess(s.index('if (copied_via_delegate || only_use_embedder_screenshot)'), s.index('IsSurfaceAvailableForCopy()'))
        self.assertIn('kBrowserNotEmbeddingValidSurfaceId', s)
        self.assertIn('ShouldSkipScreenshotWithMissReason', s)

    def test_valid_destination_preferred_else_only_safe_outgoing_blur(self):
        s = self.source('back_forward_transition_animation_manager_android.cc')
        start = s.index('  // Sandium: prefer the real destination')
        end = s.index('  CHECK(animator_factory_);', start)
        gate = s[start:end]
        self.assertIn('destination_entry->GetUserData(NavigationEntryScreenshot::kUserDataKey)', gate)
        self.assertIn('screenshot && screenshot->IsValid()', gate)
        self.assertIn('screenshot->dimensions_without_compression() ==', gate)
        self.assertIn('GetPhysicalBackingSize()', gate)
        self.assertIn('if (!sandium_has_preview && !sandium_can_blur_current)', gate)
        self.assertIn('.SchemeIsHTTPOrHTTPS()', gate)
        self.assertIn('sandium_view->IsShowing()', gate)
        self.assertIn('surface_id().is_valid()', gate)
        self.assertIn('sandium_embedder_content.reset()', gate)
        self.assertIn('if (!sandium_has_preview &&\n      (sandium_embedder_content.width()', gate)
        self.assertIn('return;', gate)
        self.assertLess(s.index('destination_entry_id_ ='), start)
        self.assertLess(s.index('!ShouldAnimateNavigationTransition'), start)

    def test_direct_navigation_cancellation_and_chained_back_unchanged(self):
        p = 'content/browser/navigation_transitions/back_forward_transition_animation_manager_android.cc'
        original = (FIXTURES/p).read_text()
        current = self.outputs[p]
        for name in ('OnGestureInvoked', 'OnGestureCancelled', 'OnGestureProgressed'):
            start = original.index('void BackForwardTransitionAnimationManagerAndroid::'+name)
            end = original.index('\n}\n', start)+3
            self.assertIn(original[start:end], current)
        self.assertIn('AnimationAbortReason::kChainedBack', current)
        self.assertIn('navigation_controller_->GoToIndex(index);', current)

    def test_internal_fallback_is_defensively_rebranded(self):
        s = self.source('TabWebContentsDelegateAndroidImpl.java')
        self.assertNotIn('R.drawable.chromelogo16', s)
        self.assertIn('R.drawable.sandium_toolbar_mark', s)

    def test_native_url_identity_cache_and_lifecycle_guards_unchanged(self):
        p = 'content/browser/renderer_host/navigation_transitions/navigation_transition_utils.cc'
        before = (FIXTURES/p).read_text()
        after = self.outputs[p]
        for name in ('void CacheScreenshotImpl(', 'bool ShouldSkipScreenshotWithMissReason('):
            start = before.index(name)
            end = before.index('\n}\n', start)+3
            self.assertIn(before[start:end], after)
        # No changes to memory budgets, eviction policy, BFCache or native URL guards.
        paths = {p for p, _, _ in m.CHANGES}
        for suffix in ('navigation_entry_screenshot_cache.cc', 'NativePageBitmapCapturer.java', 'back_forward_cache_impl.cc'):
            self.assertFalse(any(p.endswith(suffix) for p in paths))

    def test_real_blur_only_on_outgoing_clone_no_logo(self):
        s = self.source('back_forward_transition_animator.cc')
        self.assertIn('cc::slim::Filter::CreateBlur(', s)
        self.assertIn('DipToPx(10), SkTileMode::kClamp', s)
        self.assertIn('surface->SetSurfaceId(current_surface->surface_id()', s)
        self.assertIn('native_content->SetBitmap(embedder_content)', s)
        self.assertIn('bool should_draw_rrect = false;', s)
        self.assertNotIn('screenshot_layer->SetBackgroundColor(\n        fallback_ux_->color_config.background_color)', s)
        self.assertIn('if (rounded_rectangle_)', s)

    def test_cached_snapshot_and_readiness_crossfade_unchanged(self):
        p = 'content/browser/navigation_transitions/back_forward_transition_animator.cc'
        before = (FIXTURES/p).read_text()
        after = self.outputs[p]
        start = before.index('    auto* cache = nav_controller->GetNavigationEntryScreenshotCache();', before.index('void BackForwardTransitionAnimator::SetupForScreenshotPreview'))
        end = before.index('  screenshot_layer_->SetIsDrawable', start)
        self.assertIn(before[start:end], after)
        for marker in ('InitializeEffectForCrossfadeAnimation();', 'State::kWaitingForNewRendererToDraw', 'UnregisterNewFrameActivationObserver();'):
            self.assertIn(marker, after)
        # Blur uses fallback ownership and cannot be restored into destination cache.
        self.assertIn('if (!fallback_ux_) {', after)
        self.assertIn('SetUpEmbedderContentLayerIfNeeded(std::move(embedder_content));', after)

if __name__ == '__main__':
    unittest.main()
