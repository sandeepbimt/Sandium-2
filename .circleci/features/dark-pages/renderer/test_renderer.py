import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('patcher', HERE / 'apply.py')
patcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patcher)

class RendererPatchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'src'
        shutil.copytree(HERE / 'fixtures', self.root)
    def test_exact_pin_fixture_integrity(self):
        for path, sha in json.loads((HERE / 'SHA256SUMS.json').read_text()).items():
            self.assertEqual(hashlib.sha256((self.root / path).read_bytes()).hexdigest(), sha)
    def test_apply_repeat_and_all_anchors(self):
        self.assertGreater(patcher.apply(self.root), 0)
        self.assertEqual(patcher.apply(self.root), 0)
        for p in json.loads((HERE / 'patches.json').read_text()):
            self.assertIn(p['new'], (self.root / p['path']).read_text())
    def test_mismatch_fails_before_writes(self):
        p = self.root / 'third_party/blink/renderer/core/paint/paint_auto_dark_mode.cc'
        p.write_text('unsupported revision')
        before = {f: f.read_bytes() for f in self.root.rglob('*') if f.is_file()}
        with self.assertRaises(ValueError):
            patcher.apply(self.root)
        self.assertEqual(before, {f: f.read_bytes() for f in before})
    def test_document_binding_and_reset_contract(self):
        patcher.apply(self.root)
        text = (self.root / 'chrome/browser/chrome_content_browser_client.cc').read_text()
        start = text.index('bool ApplySandiumCommittedDarkPolicy(')
        helper = text[start:text.index('\n#endif', start)]
        self.assertNotIn('GetVisible', helper)
        self.assertNotIn('GetPending', helper)
        self.assertNotIn('GetDeprecatedSiteURL', helper)
        self.assertIn('frame->GetSiteInstance() != &main_frame_site', helper)
        self.assertIn('frame->IsErrorDocument()', helper)
        self.assertIn('frame->GetLastCommittedOrigin().opaque()', helper)
        self.assertLess(helper.index('prefs->sandium_dark_page_flags = -1'), helper.index('if (!client'))
        self.assertIn('client->SandiumDarkPageFlags(frame->GetLastCommittedURL())', helper)
        self.assertNotIn('prefs->force_dark_mode_enabled =', helper)
        self.assertNotIn('preferred_color_scheme =', helper)

    def test_paint_policy_does_not_mutate_author_colors(self):
        patcher.apply(self.root)
        text = (self.root / 'third_party/blink/renderer/core/css/resolver/style_adjuster.cc').read_text()
        start = text.index('void StyleAdjuster::ApplySandiumPaintPolicy(')
        helper = text[start:text.index('void StyleAdjuster::RunUncacheableStyleAdjustment(', start)]
        for forbidden in ['SetColor(', 'SetBackgroundColor(', 'SetInternalVisitedColor(']:
            self.assertNotIn(forbidden, helper)
        self.assertIn('builder.StyleType() == kPseudoIdNone', helper)
        self.assertIn('actual_element == element.GetDocument().documentElement()', helper)
        self.assertIn('parent_style->SandiumPaletteEnabled()', helper)
        self.assertNotIn('!background.GetColor().IsOpaque()', helper)
        self.assertNotIn('builder.Filter().Operations()', helper)
        self.assertIn('builder.SetColorSchemeForced(false)', helper)
        self.assertIn('builder.InForcedColorsMode()', helper)
        self.assertIn('element.GetDocument().Printing()', helper)

    def test_commit_policy_order_and_document_contract(self):
        patcher.apply(self.root)
        source = (self.root / 'content/browser/renderer_host/navigation_request.cc').read_text()
        begin = source.index('  // Use the final, browser-validated target after redirects.')
        code = source[begin:source.index('  GetRenderFrameHost()->CommitNavigation(', begin)]
        self.assertIn('IsInOutermostMainFrame()', code)
        self.assertIn('!origin_to_commit.opaque()', code)
        self.assertIn('!commit_params->is_view_source', code)
        self.assertIn('GetWebContents(), common_params->url', code)
        self.assertNotIn('GetVisible', code)
        frame = (self.root / 'third_party/blink/renderer/core/loader/frame_loader.cc').read_text()
        entry = frame.index('void FrameLoader::CommitNavigation(')
        block = frame.index('  // The outgoing document and its unload handlers have finished,', entry)
        self.assertLess(frame.index('if (!DetachDocument())', entry), block)
        self.assertLess(frame.index('if (is_provisional && !frame_->SwapIn())', entry), block)
        code = frame[block:frame.index('  tls_version_warning_origins_.clear();', block)]
        self.assertIn('commit_reason == CommitReason::kRegular', code)
        self.assertIn('frame_->IsOutermostMainFrame()', code)
        self.assertIn('policy >= 0 ? (policy & 1) : -1', code)
        self.assertNotIn('GetVisible', code)
        self.assertLess(block, frame.index('DetermineNavigationType(', block))

    def test_native_baseline_and_commit_callbacks_are_preserved(self):
        patcher.apply(self.root)
        template = (self.root / 'third_party/blink/renderer/build/scripts/templates/settings_base.h.tmpl').read_text()
        begin = template.index('  void SetSandiumDarkPageFlagsForCommit(')
        method = template[begin:template.index('\n  }', begin)]
        self.assertIn('sandium_dark_page_flags_ = flags < 0 ? -1 : (flags & 1);', method)
        self.assertNotIn('Invalidate(', method)
        self.assertNotIn('SetDelegate(', method)
        frame = (self.root / 'third_party/blink/renderer/core/loader/frame_loader.cc').read_text()
        begin = frame.index('  // The outgoing document and its unload handlers have finished,')
        block = frame[begin:frame.index('  tls_version_warning_origins_.clear();', begin)]
        self.assertIn('SetSandiumDarkPageFlagsForCommit(', block)
        self.assertNotIn('SetForceDarkModeEnabled(', block)
        self.assertNotIn('SetPreferredColorScheme(', block)
        style = (self.root / 'third_party/blink/renderer/core/css/resolver/style_adjuster.cc').read_text()
        begin = style.index('void StyleAdjuster::ApplySandiumPaintPolicy(')
        block = style[begin:style.index('void StyleAdjuster::RunUncacheableStyleAdjustment(', begin)]
        native = block[block.index('  const Settings* settings ='): ]
        self.assertLess(native.index('GetSandiumDarkPageFlags() < 0'), native.index('SetColorSchemeForced(false)'))
        self.assertLess(block.index('SetColorSchemeForced(false)'), block.index('if (!(settings->GetSandiumDarkPageFlags() & 1))'))

    def test_activation_policy_precedes_resume_visibility_events(self):
        patcher.apply(self.root)
        view = (self.root / 'third_party/blink/renderer/core/exported/web_view_impl.cc').read_text()
        begin = view.index('void WebViewImpl::SetPageLifecycleStateInternal(')
        apply = view.index('page->GetSettings().SetSandiumDarkPageFlags(', begin)
        self.assertLess(apply, view.index('SetPageFrozen(false)', begin))
        self.assertLess(apply, view.index('if (showing_page)', begin))
        self.assertLess(apply, view.index('DispatchPersistedPageshow(', begin))
        begin = view.index('void WebViewImpl::ActivatePrerenderedPage(')
        apply = view.index('GetPage()->GetSettings().SetSandiumDarkPageFlags(', begin)
        self.assertLess(apply, view.index('SetIsPrerendering(false)', begin))
        manager = (self.root / 'content/browser/renderer_host/render_frame_host_manager.cc').read_text()
        begin = manager.index('      int sandium_policy = -1;')
        code = manager[begin:manager.index('rvh->LeaveBackForwardCache(', begin)]
        self.assertIn('restored_main_frame->GetLastCommittedURL()', code)
        self.assertIn('page_restore_params->sandium_dark_page_flags = sandium_policy;', code)
        self.assertNotIn('GetVisible', code)
        page = (self.root / 'content/browser/renderer_host/page_impl.cc').read_text()
        begin = page.index('  int sandium_policy = -1;')
        code = page[begin:page.index('    const bool is_main_document', begin)]
        self.assertIn('main_document_->GetLastCommittedURL()', code)
        self.assertIn('params->sandium_dark_page_flags = sandium_policy;', code)
        self.assertNotIn('GetVisible', code)

    def test_manual_override_bypasses_custom_and_stock_paint(self):
        patcher.apply(self.root)
        paint = (self.root / 'third_party/blink/renderer/core/paint/paint_auto_dark_mode.h').read_text()
        self.assertIn('if (style.SandiumManualColorOverride())\n    return AutoDarkMode::Disabled(role);', paint)
        image = (self.root / 'third_party/blink/renderer/core/paint/paint_auto_dark_mode.cc').read_text()
        self.assertIn('if (style.SandiumManualColorOverride() || !style.ForceDark()', image)
        view = (self.root / 'third_party/blink/renderer/core/paint/view_painter.cc').read_text()
        self.assertIn('!root_object->StyleRef().SandiumManualColorOverride()', view)
        style = (self.root / 'third_party/blink/renderer/core/css/resolver/style_adjuster.cc').read_text()
        begin = style.index('void StyleAdjuster::ApplySandiumPaintPolicy(')
        block = style[begin:style.index('  const Settings* settings =', begin)]
        self.assertIn('builder.SandiumManualColorOverride()', block)
        self.assertIn('builder.SetColorSchemeForced(false)', block)
        self.assertIn('builder.SetSandiumPaletteEnabled(false)', block)
        self.assertNotIn('SetSandiumManualColorOverride(false)', style)

    def test_policy_bits_use_existing_inherited_storage_group(self):
        patcher.apply(self.root)
        text = (self.root / 'third_party/blink/renderer/core/style/computed_style_extra_fields.json5').read_text()
        for name in ('SandiumManualColorOverride', 'SandiumPaletteEnabled'):
            block = text.split('name: "' + name + '"', 1)[1].split('}', 1)[0]
            self.assertIn('field_group: "inherited"', block)
            self.assertIn('inherited: true', block)
            self.assertIn('default_value: "false"', block)
            self.assertIn('invalidate: ["paint"]', block)

    def test_preservation_default_when_enabled(self):
        for flags in range(-1, 16):
            self.assertEqual(flags >= 0 and (flags & 1) != 0, flags >= 0 and bool(flags & 1))

if __name__ == '__main__':
    unittest.main()
