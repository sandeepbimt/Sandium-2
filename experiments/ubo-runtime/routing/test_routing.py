import importlib.util,subprocess,tempfile,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('routing_apply',HERE/'apply.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
CORE=Path('/workspace/scratch/40acbbeff193/brave-core-audit')
class Tests(unittest.TestCase):
 def test_owner_no_live_switch(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);(p/'test.cc').write_text('''#include "owner_state.h"
#include <cassert>
int main(){using sandium_ubo::OwnerState;
OwnerState n;assert(n.SealAndUseNative());assert(!n.PrepareUbo(1,true));
OwnerState u;assert(!u.PrepareUbo(0,true));assert(!u.PrepareUbo(1,false));assert(u.PrepareUbo(1,true));assert(!u.SealAndUseNative());u.Invalidate(2);assert(u.restart_required());assert(!u.SealAndUseNative());assert(!u.PrepareUbo(2,true));assert(u.AcknowledgeSettings(2));assert(u.generation()==2);assert(!u.restart_required());assert(!u.SealAndUseNative());
OwnerState pre;assert(pre.PrepareUbo(1,true));pre.Invalidate(2);assert(pre.SealAndUseNative());}
''')
   subprocess.run(['g++','-std=c++17','-I',str(HERE),str(p/'test.cc'),'-o',str(p/'test')],check=True)
   subprocess.run([str(p/'test')],check=True)
 def test_pinned_overlay_and_reset(self):
  names=['browser/net/brave_ad_block_tp_network_delegate_helper.cc','browser/net/brave_ad_block_csp_network_delegate_helper.cc','components/brave_shields/content/browser/domain_block_navigation_throttle.cc','browser/cosmetic_filters/cosmetic_filters_tab_helper.cc','browser/brave_content_browser_client.cc','components/cosmetic_filters/browser/cosmetic_filters_resources.h','components/cosmetic_filters/browser/cosmetic_filters_resources.cc','browser/sources.gni','components/brave_shields/content/browser/BUILD.gn']
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);before={}
   for name in names:
    b=subprocess.check_output(['git','-C',str(CORE),'show','44a84b1f:'+name]);before[name]=b;p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
   m.apply(root);m.apply(root)
   for name in names[:3]:self.assertIn('SealAndUseNativeAdEngine',(root/name).read_text())
   picker='browser/cosmetic_filters/cosmetic_filters_tab_helper.cc'
   self.assertEqual((root/picker).read_bytes(),before[picker])
   resources=(root/'components/cosmetic_filters/browser/cosmetic_filters_resources.cc').read_text()
   self.assertEqual(resources.count('if (!use_native_ad_engine_)'),2)
   self.assertNotIn('BrowserContext',resources)
   m.reset(root);m.reset(root)
   for name,b in before.items():self.assertEqual((root/name).read_bytes(),b)
if __name__=='__main__':unittest.main()
