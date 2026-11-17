"""Exercise the production merge helper; Chromium UTF-8 predicate is stubbed.
Source guards check provider access stays one synchronous UI-thread transaction.
"""
import pathlib,subprocess,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
class Append(unittest.TestCase):
 def test_synchronous_private_guard(self):
  text=(ROOT/'native/sandium_element_colors_utils.cc').read_text()
  body=text.split('static bool JNI_SandiumElementColorsUtils_AppendAdRules(',1)[1].split('static std::string JNI_',1)[0]
  self.assertIn('DCHECK_CURRENTLY_ON(content::BrowserThread::UI)',body)
  self.assertIn('profile->IsOffTheRecord()',body)
  self.assertNotIn('PostTask',body)
  self.assertNotIn('BindOnce',body)
  self.assertLess(body.index('GetCustomFilters()'),body.index('UpdateCustomFilters('))
 def test_merge_runtime(self):
  text=(ROOT/'native/sandium_element_colors_utils.cc').read_text()
  helper='std::optional<std::string> MergeCustomAdRules'+text.split('std::optional<std::string> MergeCustomAdRules',1)[1].split('static bool JNI_',1)[0]
  source='''#include <string>
#include <optional>
#include <cassert>
namespace base {bool IsStringUTF8(const std::string& s){return s.find(char(255))==std::string::npos;}}
'''+helper+r'''
int main(){
 assert(MergeCustomAdRules("", "a")=="a");
 assert(MergeCustomAdRules("a", "b")=="a\nb");
 assert(MergeCustomAdRules("a\n", "b")=="a\nb");
 assert(MergeCustomAdRules("a\nb", "b")=="a\nb");
 assert(MergeCustomAdRules("a\nb", "a\nb")=="a\nb");
 assert(MergeCustomAdRules("a", "")=="a");
 assert(MergeCustomAdRules("a", "!#if test\n||x^\n!#endif")=="a\n!#if test\n||x^\n!#endif");
 assert(!MergeCustomAdRules("a", std::string("b\0c",3)));
 assert(!MergeCustomAdRules(std::string("b\0c",3), "a"));
 assert(!MergeCustomAdRules("a", std::string(1,char(255))));
 constexpr size_t limit=8*1024*1024;
 assert(!MergeCustomAdRules("",std::string(limit+1,'a')));
 assert(!MergeCustomAdRules(std::string(limit,'a'),"b"));
 assert(!MergeCustomAdRules(std::string(limit-1,'a'),"b"));
 assert(MergeCustomAdRules(std::string(limit-2,'a'),"b")->size()==limit);
 assert(MergeCustomAdRules(std::string(limit-2,'a')+"\n","b")->size()==limit);
 // Preserve two distinct snapshots, including conditional blocks, verbatim.
 assert(MergeCustomAdRules("!#if x\na\n!#endif", "!#if y\nb\n!#endif") == "!#if x\na\n!#endif\n!#if y\nb\n!#endif");
}
'''
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d)/'test.cc';p.write_text(source)
   run=subprocess.run(['c++','-std=c++20','-Wall','-Wextra','-Werror',str(p),'-o',d+'/test'],capture_output=True,text=True)
   self.assertEqual(run.returncode,0,run.stderr)
   run=subprocess.run([d+'/test'],capture_output=True,text=True);self.assertEqual(run.returncode,0,run.stderr)
if __name__=='__main__':unittest.main()
