"""Compile generated URL predicate against declarations from exact pinned KURL.
This checks API spelling/signatures, not a full Blink/Android compilation.
"""
from test_native import HERE,load
from pathlib import Path
import re,subprocess,tempfile,unittest
native=load('api_native',HERE/'apply.py');oopif=load('api_oopif',HERE/'oopif.py')
class NativeApi(unittest.TestCase):
 def test_real_kurl_declarations_match_emitted_predicate(self):
  header=(HERE/'fixtures/third_party/blink/renderer/platform/weborigin/kurl.h').read_text()
  required=['ProtocolIsInHttpFamily','IsAboutBlankUrl','IsAboutSrcdocUrl']
  declarations=[]
  for name in required:
   match=re.search(r'  bool '+name+r'\(\) const;',header)
   self.assertIsNotNone(match,name);declarations.append(match.group(0))
  predicate=next(new for path,old,new in oopif.PATCHES if path.endswith('dom/document.cc')).strip()
  self.assertTrue(predicate.endswith(') {'))
  predicate=predicate[:-3] # Remove enclosing if suffix; preserve the actual Boolean expression.
  cpp='class KURL {public:\n'+'\n'.join(declarations)+'''
};
struct Tree {void* Parent() const;};
struct Frame {const struct Tree& Tree()const;};
struct Document {const KURL& Url()const;const Frame* GetFrame()const;
bool eligible()const{return '''+predicate+''';}};
'''
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'api.cc';path.write_text(cpp)
   subprocess.run(['c++','-std=c++17','-Wall','-Wextra','-Werror','-fsyntax-only',str(path)],check=True)
  generated='\n'.join(new for _,_,new in native.PATCHES+oopif.PATCHES)
  self.assertNotIn('ProtocolIsInHTTPFamily',generated)
 def test_reset_owns_document_and_fixture_confirms_frame_api(self):
  import json
  inventory=json.loads((HERE.parent/'integration-plan.json').read_text())
  self.assertIn('third_party/blink/renderer/core/dom/document.cc',inventory['chromium_restore'])
  doc=(HERE/'fixtures/third_party/blink/renderer/core/dom/document.cc').read_text()
  for token in ('Url().ProtocolIsInHttpFamily()', 'GetFrame()->Tree().Parent()',
                'Url().IsAboutBlankUrl()', 'urlForBinding().IsAboutSrcdocUrl()'):
   self.assertIn(token,doc)
if __name__=='__main__':unittest.main()
