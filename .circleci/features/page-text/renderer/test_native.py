import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
DARK = HERE.parents[1] / 'dark-pages/renderer'
def load(name, file):
    spec = importlib.util.spec_from_file_location(name, file)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value
patcher = load('page_text_patcher', HERE/'apply.py')
dark = load('page_text_dark_dependency', DARK/'apply.py')

class NativeCompositionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)/'src'
        shutil.copytree(DARK/'fixtures', self.root)
        shutil.copytree(HERE/'fixtures', self.root, dirs_exist_ok=True)
        dark.apply(self.root)

    def test_exact_pin_additional_fixtures(self):
        for name, sha in json.loads((HERE/'SHA256SUMS.json').read_text()).items():
            self.assertEqual(hashlib.sha256((HERE/'fixtures'/name).read_bytes()).hexdigest(), sha)

    def test_apply_idempotent(self):
        self.assertGreater(patcher.apply(self.root), 0)
        self.assertEqual(patcher.apply(self.root), 0)
        for path, _, replacement in patcher.PATCHES:
            self.assertIn(replacement, (self.root/path).read_text())

    def test_failure_is_atomic(self):
        path = self.root/'third_party/blink/renderer/core/dom/document.cc'
        path.write_text('unsupported revision')
        before = {f:f.read_bytes() for f in self.root.rglob('*') if f.is_file()}
        with self.assertRaises(ValueError): patcher.apply(self.root)
        self.assertEqual(before, {f:f.read_bytes() for f in before})

    def test_commit_and_style_order(self):
        patcher.apply(self.root)
        frame = (self.root/'third_party/blink/renderer/core/loader/frame_loader.cc').read_text()
        entry = frame.index('void FrameLoader::CommitNavigation(')
        setting = frame.index('settings->SetSandiumPageTextPolicyForCommit', entry)
        self.assertLess(frame.index('if (!DetachDocument())', entry), setting)
        self.assertLess(setting, frame.index('tls_version_warning_origins_.clear();', setting))
        doc = (self.root/'third_party/blink/renderer/core/dom/document.cc').read_text()
        entry = doc.index('void Document::Initialize()')
        self.assertLess(doc.index('sandium-page-text-v1', entry),
                        doc.index('StyleForViewport()', entry))
        self.assertIn('WebCssOrigin::kUser', doc[entry:entry+2500])
        self.assertIn('IsOutermostMainFrame()', doc[entry:entry+2500])

    def test_native_scale_does_not_overwrite_accessibility(self):
        patcher.apply(self.root)
        font = (self.root/'third_party/blink/renderer/core/css/resolver/font_builder.cc').read_text()
        entry = font.index('float FontBuilder::GetComputedSizeFromSpecifiedSize(')
        end = font.index('void FontBuilder::CheckForGenericFamilyChange', entry)
        body = font[entry:end]
        self.assertNotIn('SandiumPageText', body)
        self.assertFalse(any('font_builder.cc' in p[0] for p in patcher.PATCHES))
        self.assertIn('frame->TextZoomFactor()', body)
        self.assertIn('builder.GetTextSizeAdjust().Multiplier()', body)
        self.assertIn('font_description.IsAbsoluteSize(),\n      specified_size', body)
        for _, _, patch in patcher.PATCHES:
            self.assertNotIn('SetAccessibilityFontScaleFactor(', patch)
            self.assertNotIn('SetZoomFactors(', patch)
            self.assertNotIn('SetPageScaleFactor(', patch)

    def test_no_activation_or_script_hooks(self):
        names = [p[0] for p in patcher.PATCHES]
        self.assertFalse(any('page_impl.cc' in x or 'render_frame_host_manager.cc' in x
                             or 'web_view_impl.cc' in x for x in names))
        joined = '\n'.join(x[2] for x in patcher.PATCHES)
        for forbidden in ('evaluateJavaScript', 'MutationObserver', 'onPageLoadFinished',
                          'onShown(', 'SetSandiumDarkPageFlagsForCommit('):
            self.assertNotIn(forbidden, joined)
        self.assertNotIn('font-size', patcher.CSS)
        self.assertNotIn('font-family', patcher.CSS)
        self.assertNotIn('line-height', patcher.CSS)

    def test_java_and_native_stylesheet_agree(self):
        java_root = HERE.parent/'java/org/chromium/chrome/browser/sandium/text'
        output = Path(self.tmp.name)/'classes'; output.mkdir()
        source = Path(self.tmp.name)/'Dump.java'
        source.write_text('''import org.chromium.chrome.browser.sandium.text.*;
public class Dump { public static void main(String[] args) {
System.out.print(PageTextStylesheet.compile(new PageTextPolicy.Settings(true,100,true)));
}}''')
        subprocess.run(['java','com.sun.tools.javac.Main','-d',str(output),
                        str(java_root/'PageTextPolicy.java'),
                        str(java_root/'PageTextStylesheet.java'),str(source)],check=True)
        result = subprocess.run(['java','-cp',str(output),'Dump'],check=True,
                                capture_output=True,text=True)
        self.assertEqual(result.stdout, patcher.CSS)

    def test_settings_decode_and_independent_factor_cpp(self):
        source = next(p[2] for p in patcher.PATCHES if p[0].endswith('settings_base.h.tmpl'))
        source = source[:source.index('  void SetFromStrings')]
        cpp = '''#include <cassert>
#include <cmath>
struct Settings { int sandium_page_text_policy_ = 100;
''' + source + '''};
int main() {
  Settings s;
  assert(s.SandiumPageTextScalePercent()==100);
  assert(!s.SandiumPageTextJustifyEnabled());
  for(int scale=75;scale<=150;scale+=5) {
    for(int flags : {0,256,512,768}) {
      s.SetSandiumPageTextPolicyForCommit(scale|flags);
      assert(s.SandiumPageTextScalePercent()==scale);
      assert(s.SandiumPageTextJustifyEnabled()==(flags==768));
    }
  }
  for(int bad : {-1,0,74,151,101,1024,4095}) {
    s.SetSandiumPageTextPolicyForCommit(bad);
    assert(s.SandiumPageTextScalePercent()==100);
    assert(!s.SandiumPageTextJustifyEnabled());
  }
  s.SetSandiumPageTextPolicyForCommit(125);
  assert(s.SandiumPageTextScalePercent()==125);
  assert(!s.SandiumPageTextJustifyEnabled());
  // Default next document clears policy; restore never calls the setter.
  s.SetSandiumPageTextPolicyForCommit(100);
  assert(s.SandiumPageTextScalePercent()==100);
}
'''
        cpp = '#include <initializer_list>\n' + cpp
        path = Path(self.tmp.name)/'policy.cc'; path.write_text(cpp)
        binary = Path(self.tmp.name)/'policy'
        subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-Werror',str(path),'-o',str(binary)],check=True)
        subprocess.run([str(binary)],check=True)

    def test_native_css_uses_supported_android_property(self):
        patcher.apply(self.root)
        prefs=(self.root/'third_party/blink/public/common/web_preferences/web_preferences.h').read_text()
        self.assertIn('bool text_size_adjust_enabled = BUILDFLAG(IS_ANDROID);',prefs)
        doc=(self.root/'third_party/blink/renderer/core/dom/document.cc').read_text()
        i=doc.index('StringBuilder css;')
        end=doc.index('if (!css.empty())',i)
        body=doc[i:end]
        self.assertIn('settings->GetTextSizeAdjustEnabled()',body)
        self.assertIn('settings->SandiumPageTextScalePercent() != 100',body)
        self.assertIn('text-size-adjust:',body)
        self.assertNotIn('font-size:',body)
        self.assertNotIn('font-family:',body)
        # Existing engine is unchanged, including native accessibility/minimum logic.
        baseline=(HERE/'fixtures/third_party/blink/renderer/core/css/resolver/font_builder.cc').read_text()
        self.assertEqual(baseline,(self.root/'third_party/blink/renderer/core/css/resolver/font_builder.cc').read_text())

if __name__ == '__main__': unittest.main()
