"""Keep pinned Brave wrapper hooks when typography adds raw reset owners."""
from test_native import HERE,DARK,load
from pathlib import Path
import hashlib,json,subprocess,tempfile,shutil,unittest
ROOT=HERE.parents[3]
dark=load('brave_patch_dark',ROOT/'.circleci/scripts/apply-sandium-dark-combined.py')
text=load('brave_patch_text',HERE.parent/'apply.py')
popup=load('brave_patch_popup',ROOT/'.circleci/scripts/apply-sandium-shields-popup.py')
java=load('brave_patch_java',ROOT/'.circleci/scripts/apply-sandium-dark-pages.py')
class BraveReplay(unittest.TestCase):
 def test_every_matching_pinned_patch_has_reset_mapping(self):
  inventory=json.loads((HERE.parent/'integration-plan.json').read_text())
  recipe=json.loads((ROOT/'.circleci/features/removal-recipe.json').read_text())
  expected={'content/browser/renderer_host/navigation_controller_impl.cc',
   'content/browser/renderer_host/navigation_request.cc',
   'content/browser/renderer_host/render_frame_host_impl.cc',
   'content/public/browser/content_browser_client.h','content/renderer/render_frame_impl.cc',
   'third_party/blink/renderer/core/dom/document.cc'}
  self.assertEqual(set(inventory['chromium_restore_patches']),expected)
  for path,patch in inventory['chromium_restore_patches'].items():
   self.assertEqual(recipe['chromium_restore_patches'].get(path),patch)
 def test_real_brave_hunks_survive_complete_typography_composition(self):
  with tempfile.TemporaryDirectory() as temp:
   src=Path(temp)
   for folder in (DARK/'fixtures',ROOT/'tests/fixtures/dark-pages',HERE/'fixtures',HERE/'oopif-fixtures'):
    shutil.copytree(folder,src,dirs_exist_ok=True)
   for name,sha in json.loads((HERE/'BRAVE_PATCH_SHA256SUMS.json').read_text()).items():
    data=(HERE/'brave-patch-fixtures'/name).read_bytes();self.assertEqual(hashlib.sha256(data).hexdigest(),sha)
    subprocess.run(['git','apply','--check','-'],cwd=src,input=data,check=True,capture_output=True)
    subprocess.run(['git','apply','-'],cwd=src,input=data,check=True,capture_output=True)
   layout=src/'brave'/java.LAYOUT;layout.write_text(popup.layout(layout.read_text()))
   handler=src/'brave'/java.SHIELDS;handler.write_text(popup.java(handler.read_text()))
   for transform in (dark,text):
    for p,s in transform.compose(src,ROOT).items():p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s)
   self.assertTrue(all(p.read_text()==s for p,s in text.compose(src,ROOT).items()))
   doc=(src/'third_party/blink/renderer/core/dom/document.cc').read_text()
   self.assertEqual(doc.count('result = RewriteBraveToChrome(result);'),1)
   self.assertIn('sandium-page-text-v1',doc)
   rfhi=(src/'content/browser/renderer_host/render_frame_host_impl.cc').read_text()
   for hook in ('COMPUTE_ISOLATION_INFO_INTERNAL','COMPUTE_NONCE','CREATE_NEW_WINDOW'):
    self.assertEqual(rfhi.count('BRAVE_RENDER_FRAME_HOST_IMPL_'+hook),1)
   self.assertIn('GetPage().SetSandiumPageTextPolicyForNewDocument',rfhi)
if __name__=='__main__':unittest.main()
