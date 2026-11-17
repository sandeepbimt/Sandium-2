import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

MODULE = Path(__file__).parents[1] / "apply-typography-policy.py"
spec = importlib.util.spec_from_file_location("typography_policy", MODULE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class Tests(unittest.TestCase):
    def test_strict_and_idempotent(self):
        original = "before\n" + m.ANCHOR + "\nafter"
        result = m.transform(original)
        self.assertEqual(m.transform(result), result)
        for bad in ("", original + original, original + "SANDIUM_DIAGNOSTIC_TYPOGRAPHY_DISPATCH_V1"):
            with self.assertRaises(ValueError):
                m.transform(bad)

    def test_numeric_contract_and_gate_compiles(self):
        harness = r"""
#include <cassert>
#include <vector>
struct Params { int sandium_page_text_policy=868; } params;
struct Client {
 bool enabled=false; int calls=0; std::vector<double> fields;
 bool IsSandiumNavigationDiagnosticsEnabled(void*) { return enabled; }
 void RecordSandiumNavigationDiagnostic(void*,int code,long nav,long tick,
                                       std::vector<double> values) {
   assert(code==26 && nav==42 && tick==123); calls++; fields=values;
 }
 Client* browser() { return this; }
} client;
Client* GetContentClient(){return &client;}
void* GetWebContents(){return nullptr;}
long GetNavigationId(){return 42;}
bool outer=true;
bool IsInOutermostMainFrame(){return outer;}
namespace base { struct TimeTicks {
 static TimeTicks Now(){return {};}
 TimeTicks since_origin(){return {};}
 long InMicroseconds(){return 123;}
}; }
void emit() { auto* commit_params=&params;
""" + m.BODY + r"""
}
int main(){
 emit(); assert(client.calls==0);
 client.enabled=true; emit();
 assert(client.fields==std::vector<double>({868.,1.,0.}));
 outer=false;params.sandium_page_text_policy=100;emit();
 assert(client.fields==std::vector<double>({100.,0.,0.}));
}
"""
        with tempfile.TemporaryDirectory() as d:
            cpp=Path(d)/"test.cc";exe=Path(d)/"test";cpp.write_text(harness)
            subprocess.run(["c++","-std=c++17","-Wall","-Werror",str(cpp),"-o",str(exe)],check=True)
            subprocess.run([str(exe)],check=True)

    def test_no_content_payload(self):
        for forbidden in ("url", "textContent", "selector", "GetLastCommittedURL"):
            self.assertNotIn(forbidden, m.BODY)

if __name__ == "__main__": unittest.main()
