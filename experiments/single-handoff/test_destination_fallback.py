"""Targeted host tests for the enabled #1426 handoff color transform."""
import ast
import subprocess
import tempfile
import unittest
from pathlib import Path
import destination_fallback as fix

HERE = Path(__file__).resolve().parent
NATIVE_SNIPPET = '''#include "content/public/common/content_features.h"
void BlurTransitionAnimationManager::ReadyToCommitNavigation(
    NavigationHandle* navigation_handle) {
  // Existing native fade, darken and bounded lifecycle are untouched.
  SkColor4f background_color = SkColors::kWhite;
  if (auto theme_color = delegate->GetThemeColor()) {
    background_color = SkColor4f::FromColor(*theme_color);
  }
  fallback_color_layer_->SetBackgroundColor(background_color);
  fallback_color_layer_->SetOpacity(0.0f);
}
'''


class DestinationFallbackTests(unittest.TestCase):
    def test_exact_native_fallback_anchor_and_replay(self):
        result = fix.transform(NATIVE_SNIPPET)
        self.assertEqual(fix.transform(result), result)
        self.assertIn('fallback_color_layer_->SetBackgroundColor(background_color);', result)
        self.assertIn('fallback_color_layer_->SetOpacity(0.0f);', result)
        self.assertEqual(result.count(fix.MARKER), 1)
        self.assertNotIn(fix.OLD, result)

    def test_shipping_diagnostic_includes_preserved_without_duplicates(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('native_diagnostics',
            HERE.parent / 'native-navigation/diagnostics.py')
        diagnostics = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(diagnostics)
        block = next(new + '\n' for path, old, new in diagnostics.NATIVE_CHANGES
            if path == fix.PATH and old == '#include "base/metrics/histogram_functions.h"')
        self.assertEqual(block, fix.DIAGNOSTIC_INCLUDES)
        source = block + NATIVE_SNIPPET
        result = fix.transform(source)
        self.assertEqual(result.count(block), 1)
        self.assertEqual(fix.transform(result), result)
        for header in ('content_browser_client.h', 'content_client.h',
                       'navigation_request.h', 'navigation_params.mojom.h'):
            self.assertEqual(result.count(header), 1)
        for invalid in (source + block, source.replace('#include <vector>', ''),
                        source.replace('#include "base/time/time.h"', ''),
                        source + '#include "content/public/common/content_client.h"'):
            with self.assertRaises(ValueError):
                fix.transform(invalid)

    def test_only_managed_dark_is_black_and_managed_light_white(self):
        result = fix.transform(NATIVE_SNIPPET)
        self.assertIn('if (sandium_dark_policy == 1) {\n    background_color = SkColors::kBlack;', result)
        self.assertIn('SkColor4f background_color = SkColors::kWhite;', result)
        self.assertIn('} else if (sandium_dark_policy < 0) {', result)
        self.assertIn('delegate->GetThemeColor()', result)

    def test_ambiguous_and_non_web_navigation_not_managed(self):
        result = fix.transform(NATIVE_SNIPPET)
        for guard in ('GetOriginToCommit()', 'origin_to_commit->opaque()',
                'SchemeIsHTTPOrHTTPS()', 'IsErrorPage()', 'IsPdf()',
                'is_view_source', 'sandium_request &&'):
            self.assertIn(guard, result)
        self.assertIn('GetSandiumDarkPageFlagsForNavigation(', result)
        self.assertIn('web_contents(), navigation_handle->GetURL()', result)
        self.assertNotIn('commit_params().sandium_dark_page_flags', result)
        self.assertNotIn('commit_params().sandium_dark_policy_revision', result)

    def test_unexpected_or_partial_source_rejected(self):
        for value in ('', NATIVE_SNIPPET + fix.OLD,
                NATIVE_SNIPPET.replace(fix.OLD, fix.NEW),
                NATIVE_SNIPPET.replace(fix.INCLUDE_ANCHOR, '')):
            with self.subTest(value=value[:35]):
                with self.assertRaises(ValueError):
                    fix.transform(value)
        with self.assertRaises(ValueError):
            fix.transform(fix.transform(NATIVE_SNIPPET) + fix.NEW)

    def test_does_not_change_navigation_or_animation_lifetime(self):
        result = fix.transform(NATIVE_SNIPPET)
        self.assertIn('Existing native fade, darken and bounded lifecycle are untouched.', result)
        for prohibited in ('SetAnimationState(', 'StartFadeOut(', 'DidFirstVisuallyNonEmptyPaint(',
                           'loadUrl(', 'postDelayed(', 'Sleep(', 'SetPageBaseBackgroundColor('):
            self.assertNotIn(prohibited, fix.NEW)

    def test_exact_color_decision_compiles_and_handles_exclusions(self):
        # The injected selector, not a rewritten model, runs against lightweight
        # C++ interfaces. This is NOT a full Chromium/Android compile.
        source = r'''#include <cassert>
#include <optional>
struct SkColor4f { int color; static SkColor4f FromColor(int value) {return {value};} };
namespace SkColors { constexpr SkColor4f kWhite{0}, kBlack{1}; }
struct Origin { bool is_opaque=false; bool opaque() const {return is_opaque;} };
struct GURL { bool web=true; bool SchemeIsHTTPOrHTTPS() const {return web;} };
struct NavigationHandle {
  GURL url; bool error=false, pdf=false, view_source=false, missing_request=false;
  std::optional<Origin> origin{Origin{}};
  auto GetOriginToCommit() const {return origin;}
  const GURL& GetURL() const {return url;}
  bool IsErrorPage() const {return error;}
  bool IsPdf() const {return pdf;}
};
struct NavigationRequest {
  struct Params {bool is_view_source;};
  Params params;
  const Params& commit_params() const {return params;}
  static NavigationRequest* From(NavigationHandle* handle) {
    static NavigationRequest request;
    request.params.is_view_source=handle->view_source;
    return handle->missing_request ? nullptr : &request;
  }
};
struct WebContents {};
struct BrowserClient {
  int policy=-1, queries=0;
  int GetSandiumDarkPageFlagsForNavigation(WebContents*, const GURL&) {
    ++queries;return policy;
  }
};
struct ContentClient {BrowserClient browser_impl;BrowserClient* browser(){return &browser_impl;}};
ContentClient content_client;
ContentClient* GetContentClient(){return &content_client;}
struct Delegate {
 std::optional<int> outgoing_theme{1};
 std::optional<int> GetThemeColor(){return outgoing_theme;}
};
SkColor4f select(NavigationHandle* navigation_handle,Delegate* delegate,WebContents* contents){
  auto web_contents=[&](){return contents;};
''' + fix.NEW + r'''  return background_color;
}
int main(){
  WebContents web; NavigationHandle nav; Delegate delegate;
  auto& browser=content_client.browser_impl;
  browser.policy=1;delegate.outgoing_theme=0;
  assert(select(&nav,&delegate,&web).color==1 && browser.queries==1);
  browser.policy=0;delegate.outgoing_theme=1;
  assert(select(&nav,&delegate,&web).color==0 && browser.queries==2);
  browser.policy=-1;assert(select(&nav,&delegate,&web).color==1 && browser.queries==3);
  delegate.outgoing_theme.reset();
  assert(select(&nav,&delegate,&web).color==0 && browser.queries==4);
  delegate.outgoing_theme=1;browser.policy=0;
  auto excluded=[&]{int before=browser.queries;
    assert(select(&nav,&delegate,&web).color==1);
    assert(browser.queries==before);};
  nav.url.web=false;excluded();nav.url.web=true;
  nav.error=true;excluded();nav.error=false;
  nav.pdf=true;excluded();nav.pdf=false;
  nav.view_source=true;excluded();nav.view_source=false;
  nav.origin=std::nullopt;excluded();nav.origin=Origin{true};excluded();nav.origin=Origin{};
  nav.missing_request=true;excluded();
}
'''
        with tempfile.TemporaryDirectory(prefix='sandium-1426-cpp-') as temp:
            source_path = Path(temp) / 'selector.cc'
            binary = Path(temp) / 'selector'
            source_path.write_text(source)
            compile_result = subprocess.run(['c++', '-std=c++20', '-Wall', '-Wextra', '-Werror',
                            str(source_path), '-o', str(binary)],
                           capture_output=True, text=True)
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            subprocess.run([str(binary)], capture_output=True, text=True, check=True)

    def test_candidate_is_wired_last_without_touching_ci(self):
        candidate = (HERE / 'candidate_plan.py').read_text()
        tree = ast.parse(candidate)
        self.assertIsNotNone(tree)
        self.assertIn("'destination_fallback'", candidate)
        self.assertIn('prepaint.plan, fallback.plan', candidate)
        self.assertIn('prepaint.PATH, fallback.PATH', candidate)


if __name__ == '__main__':
    unittest.main()
