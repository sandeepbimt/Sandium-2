"""Pinned source composition and snapshot model, not browser runtime tests."""
from test_native import HERE, DARK, load
import hashlib, json, shutil, tempfile, unittest, subprocess
from pathlib import Path
native = load('native_oopif', HERE/'apply.py')
dark = load('dark_oopif', DARK/'apply.py')
oopif = load('oopif', HERE/'oopif.py')

class OopifTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)/'src'
        for base in (DARK/'fixtures', HERE/'fixtures', HERE/'oopif-fixtures'):
            shutil.copytree(base,self.root,dirs_exist_ok=True)
        dark.apply(self.root); native.apply(self.root)
    def read(self,p): return (self.root/p).read_text()
    def test_pin(self):
        for name, sha in json.loads((HERE/'OOPIF_SHA256SUMS.json').read_text()).items():
            self.assertEqual(hashlib.sha256((HERE/'oopif-fixtures'/name).read_bytes()).hexdigest(),sha)
    def test_idempotent(self):
        self.assertGreater(oopif.apply(self.root),0)
        self.assertEqual(oopif.apply(self.root),0)
        for p,old,new in oopif.PATCHES: self.assertIn(new,self.read(p))
    def test_atomic_mismatch(self):
        (self.root/'content/browser/renderer_host/render_frame_host_impl.cc').write_text('wrong pin')
        before={p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        with self.assertRaises(ValueError): oopif.apply(self.root)
        self.assertEqual(before,{p:p.read_bytes() for p in before})
    def test_capture_after_accepted_document_reset(self):
        oopif.apply(self.root)
        s=self.read('content/browser/renderer_host/render_frame_host_impl.cc')
        pos=s.index('GetPage().SetSandiumPageTextPolicyForNewDocument(')
        start=s.rfind('if (navigated_to_new_document)',0,pos)
        self.assertGreater(start,0)
        self.assertIn('document_associated_data_.emplace(',s[start:pos])
        self.assertIn('if (is_main_frame())',s[start:pos])
        self.assertIn('!navigation_request->IsPageActivation()',s[start-1500:start])
    def test_child_uses_snapshot_not_preferences(self):
        oopif.apply(self.root)
        s=self.read('content/browser/renderer_host/navigation_request.cc')
        start=s.index('} else if (RenderFrameHostImpl* parent = frame_tree_node_->parent())')
        end=s.index('commit_params->sandium_dark_page_flags = -1;',start)
        self.assertIn('parent->GetPage().sandium_page_text_policy()',s[start:end])
        self.assertNotIn('GetSandiumPageTextPolicyForNavigation',s[start:end])
        self.assertIn('commit_params_->sandium_page_text_policy = commit_params->sandium_page_text_policy;',s[start:end])
    def test_local_root_only_before_install(self):
        oopif.apply(self.root)
        s=self.read('third_party/blink/renderer/core/loader/frame_loader.cc')
        self.assertEqual(s.count('settings->SetSandiumPageTextPolicyForCommit'),1)
        i=s.index('settings->SetSandiumPageTextPolicyForCommit')
        self.assertIn('commit_reason == CommitReason::kRegular && frame_->IsLocalRoot()',s[i-200:i])
        self.assertLess(s.index('if (!DetachDocument())'),i)
        doc=self.read('third_party/blink/renderer/core/dom/document.cc')
        i=doc.index('sandium-page-text-v1')
        self.assertNotIn('IsOutermostMainFrame',doc[i-400:i])
    def test_embedded_about_gate_is_parent_guarded(self):
        oopif.apply(self.root)
        s=self.read('third_party/blink/renderer/core/dom/document.cc')
        i=s.index('settings && (settings->SandiumPageTextJustifyEnabled()')
        end=s.index('StringBuilder css;',i)
        self.assertIn('GetFrame()->Tree().Parent()',s[i:end])
        self.assertIn('Url().IsAboutBlankUrl()',s[i:end])
        self.assertIn('Url().IsAboutSrcdocUrl()',s[i:end])
        self.assertNotIn('ProtocolIsAbout()',s[i:end])
    def test_child_error_preserves_owner_snapshot(self):
        oopif.apply(self.root)
        s=self.read('content/browser/renderer_host/render_frame_host_impl.cc')
        i=s.index('CHECK_NE(net::OK, error_code);')
        self.assertIn('GetParent() ? GetParent()->GetPage().sandium_page_text_policy() : 100',s[i:i+500])
    def test_error_canonical_policy_precedes_clone(self):
        oopif.apply(self.root)
        s=self.read('content/browser/renderer_host/navigation_request.cc')
        i=s.index('RenderFrameHostImpl* text_policy_parent =')
        end=s.index('GetRenderFrameHost()->FailedNavigation(', i)
        self.assertIn('commit_params_->sandium_page_text_policy =',s[i:end])
        self.assertIn(': 100;',s[i:end])
        self.assertIn('text_policy_parent->GetPage().sandium_page_text_policy()',s[i:end])
    def test_extracted_normalizer_and_snapshot_model(self):
        # The normalizer is production code. Page lifetime sequencing here is a
        # model of source guards, not an execution of Chromium or Mojo ordering.
        oopif.apply(self.root)
        h=self.read('content/browser/renderer_host/page_impl.h')
        a=h.index('  int sandium_page_text_policy()'); b=h.index('\n  }',a)+4
        cpp='''#include <cassert>\nstruct Page { int sandium_page_text_policy_=100;\n'''+h[a:b]+'''};
int main(){
 Page old; old.SetSandiumPageTextPolicyForNewDocument(125|768);
 int prefs=150; // Saving does not mutate the accepted document.
 assert(old.sandium_page_text_policy()==(125|768));
 int local=old.sandium_page_text_policy(), oopif=old.sandium_page_text_policy();
 assert(local==oopif); // same owner snapshot, including error child
 Page pending; pending.SetSandiumPageTextPolicyForNewDocument(prefs);
 assert(old.sandium_page_text_policy()==(125|768)); // canceled nav / BFCache
 assert(pending.sandium_page_text_policy()==150);
 for(int bad: {-1, 74, 151, 101, 1124}) {Page p;p.SetSandiumPageTextPolicyForNewDocument(bad);assert(p.sandium_page_text_policy()==100);}
 for(int pct=75;pct<=150;pct+=5) {Page p;p.SetSandiumPageTextPolicyForNewDocument(pct|768);assert(p.sandium_page_text_policy()==(pct|768));}
}'''
        cpp=cpp.replace('#include <cassert>','#include <cassert>\n#include <initializer_list>')
        p=Path(self.tmp.name)/'test.cc';p.write_text(cpp)
        binary=p.with_suffix('');subprocess.run(['c++','-std=c++17',str(p),'-o',str(binary)],check=True)
        subprocess.run([str(binary)],check=True)

if __name__=='__main__': unittest.main()
