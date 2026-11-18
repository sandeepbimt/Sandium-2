import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / 'experiments/single-handoff'
spec = importlib.util.spec_from_file_location('blue_clear', HERE / 'blue_clear.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class BlueClear(unittest.TestCase):
    def fixture(self):
        return json.loads(gzip.decompress((HERE / 'fixtures/blue-clear.json.gz').read_bytes()))

    def test_exact_pinned_full_source_and_only_intended_difference(self):
        f = self.fixture()
        self.assertEqual(f['revision'], m.PIN)
        self.assertEqual(f['path'], m.PATH)
        self.assertEqual(hashlib.sha256(f['source'].encode()).hexdigest(), f['sha256'])
        out = m.transform(f['source'])
        self.assertEqual(out.replace(m.AFTER, m.BEFORE), f['source'])
        self.assertEqual(m.transform(out), out)
        self.assertEqual(out.count(m.MARKER), 1)

    def test_drift_partial_and_duplicate_rejected(self):
        for text in (m.BEFORE.replace('SkColors::kBlue', 'SkColors::kRed'),
                     m.BEFORE + m.BEFORE, m.BEFORE + m.MARKER,
                     m.AFTER.replace('SkColors::kBlack', 'SkColors::kRed'),
                     m.AFTER + m.BEFORE):
            with self.subTest(text=text[:100]), self.assertRaises(ValueError):
                m.transform(text)

    def test_plan_is_nonmutating_and_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / m.PATH
            p.parent.mkdir(parents=True)
            source = self.fixture()['source']
            p.write_text(source)
            planned = m.plan(tmp)
            self.assertEqual(p.read_text(), source)
            self.assertEqual(set(planned), {p})
            self.assertEqual(planned[p].replace(m.AFTER, m.BEFORE), source)

    def test_actual_cpp_function_for_all_build_and_pass_branches(self):
        # Compile the actual transformed function, not a Python behaviour model.
        # ClearCanvas is observed through a stub; its implementation is untouched
        # and byte-for-byte full-source equality above protects scissor semantics.
        preamble = '''#include <cassert>
#define DCHECK_IS_ON() TEST_DCHECK
#define BUILDFLAG(flag) flag
#define IS_LINUX TEST_LINUX
namespace SkColors { enum { kTransparent=0, kBlue=1, kBlack=2 }; }
struct Pass { bool has_transparent_background=false; };
struct Frame { Pass* current_render_pass; };
class SkiaRenderer {
 public:
  Pass pass; Frame frame{&pass}; int calls=0, color=-1;
  Frame* current_frame() { return &frame; }
  void ClearCanvas(int value) { ++calls; color=value; }
  void ClearFramebuffer();
};
'''
        main = '''
int main() {
 SkiaRenderer r; r.pass.has_transparent_background=true;
 r.ClearFramebuffer(); assert(r.calls==1 && r.color==SkColors::kTransparent);
 r.calls=0; r.color=-1; r.pass.has_transparent_background=false;
 r.ClearFramebuffer();
#if TEST_DCHECK && !TEST_LINUX
 assert(r.calls==1 && r.color==EXPECTED_OPAQUE);
#else
 assert(r.calls==0 && r.color==-1);
#endif
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            cpp = Path(tmp) / 'test.cc'
            binary = Path(tmp) / 'test'
            for function, color in ((m.BEFORE, 1), (m.AFTER, 2)):
                cpp.write_text(preamble + function + main)
                for dcheck in (0, 1):
                    for linux in (0, 1):
                        subprocess.run(['c++', '-std=c++17', '-Wall', '-Werror',
                                        f'-DTEST_DCHECK={dcheck}', f'-DTEST_LINUX={linux}',
                                        f'-DEXPECTED_OPAQUE={color}', str(cpp), '-o', str(binary)], check=True)
                        subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    unittest.main()
