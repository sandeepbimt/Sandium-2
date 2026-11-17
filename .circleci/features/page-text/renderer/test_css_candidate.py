"""Compiles extracted native CSS builder and compares all policies with Java.
This validates emission/default no-op, not Blink CSS rendering or Android behavior.
"""
from test_native import HERE, DARK, load
import shutil, tempfile, subprocess, unittest
from pathlib import Path
native=load('native_css_candidate',HERE/'apply.py')
dark=load('dark_css_candidate',DARK/'apply.py')

class NativeCssCandidateTest(unittest.TestCase):
    def test_all_policy_strings_and_disabled_platform(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'src'
            shutil.copytree(DARK/'fixtures',root)
            shutil.copytree(HERE/'fixtures',root,dirs_exist_ok=True)
            dark.apply(root); native.apply(root)
            doc=(root/'third_party/blink/renderer/core/dom/document.cc').read_text()
            start=doc.index('    StringBuilder css;')
            body=doc[start:doc.index('    if (!css.empty())',start)]
            policy=next(p[2] for p in native.PATCHES if p[0].endswith('settings_base.h.tmpl'))
            policy=policy[:policy.index('  void SetFromStrings')]
            cpp='''#include <string>
#include <iostream>
#include <cassert>
#include <initializer_list>
struct Settings {int sandium_page_text_policy_=100;bool supported=true;
bool GetTextSizeAdjustEnabled()const{return supported;}
'''+policy+'''};
struct StringBuilder {std::string value;
void Append(const char* s){value+=s;} void AppendNumber(int n){value+=std::to_string(n);}
};
std::string Compile(const Settings* settings){
'''+body+'''return css.value;}
int main(){Settings s;
assert(Compile(&s).empty());
for(int size=75;size<=150;size+=5)for(int flags:{0,256,512,768}){
s.SetSandiumPageTextPolicyForCommit(size|flags);
std::cout<<size<<"|"<<flags<<"|"<<Compile(&s)<<"\\n";
}
s.SetSandiumPageTextPolicyForCommit(125);s.supported=false;
assert(Compile(&s).empty()); // no unsupported platform CSS/no force-enabling a setting
s.SetSandiumPageTextPolicyForCommit(125|768);
assert(Compile(&s).find("text-align:justify")!=std::string::npos);
assert(Compile(&s).find("text-size-adjust")==std::string::npos);
}
'''
            source=Path(tmp)/'css.cc';source.write_text(cpp);binary=Path(tmp)/'css'
            subprocess.run(['c++','-std=c++17','-Wall','-Wextra','-Werror',str(source),'-o',str(binary)],check=True)
            expected=subprocess.run([str(binary)],capture_output=True,text=True,check=True).stdout
            java=Path(tmp)/'Dump.java';java.write_text('''import org.chromium.chrome.browser.sandium.text.*;
public class Dump{public static void main(String[]args){
for(int size=75;size<=150;size+=5)for(int flags:new int[]{0,256,512,768}){
System.out.println(size+"|"+flags+"|"+PageTextStylesheet.compile(new PageTextPolicy.Settings((flags&256)!=0,size,(flags&512)!=0)));
}}}''')
            java_root=HERE.parent/'java/org/chromium/chrome/browser/sandium/text'
            out=Path(tmp)/'classes';out.mkdir()
            subprocess.run(['java','com.sun.tools.javac.Main','-d',str(out),str(java_root/'PageTextPolicy.java'),str(java_root/'PageTextStylesheet.java'),str(java)],check=True)
            actual=subprocess.run(['java','-cp',str(out),'Dump'],capture_output=True,text=True,check=True).stdout
            self.assertEqual(expected,actual)
            self.assertEqual(len(actual.splitlines()),64)

if __name__=='__main__':unittest.main()
