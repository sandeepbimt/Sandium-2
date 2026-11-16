import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('guard', ROOT/'.circleci/scripts/apply-sandium-translation-guard.py')
guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)

class TranslationGuardTests(unittest.TestCase):
    def test_exact_pinned_patch_and_idempotence(self):
        src=(ROOT/'tests/fixtures/translation-guard/library_loader_hooks.cc').read_text()
        out=guard.transform(src)
        self.assertEqual(guard.transform(out),out)
        self.assertEqual(out.count('HookJniFindClass(env);'),1)
        self.assertIn('result && library_process_type == PROCESS_BROWSER',out)
        self.assertIn('std::fclose(executable)',out)
        self.assertNotIn('ro.product.cpu',out)
        self.assertNotIn('UnhookJniFindClass',out)

    def test_unknown_source_and_partial_guard_rejected(self):
        with self.assertRaises(ValueError):guard.transform('unrecognized')
        with self.assertRaises(ValueError):guard.transform(guard.MARKER)

    def test_native_detector_cxx_matrix(self):
        compiler=shutil.which('clang++') or shutil.which('g++')
        self.assertIsNotNone(compiler,'A C++ compiler is required for guard verification')
        main=r'''
#include <cassert>
#include <cstring>
int main() {
 std::array<unsigned char,20> h{};
 h[0]=0x7f; h[1]='E'; h[2]='L'; h[3]='F'; h[4]=2; h[5]=1; h[6]=1; h[18]=62;
 assert(SandiumIsX64ProcessElf(h));
 h[18]=183; assert(!SandiumIsX64ProcessElf(h)); // real ARM64 VM
 h[18]=3; assert(!SandiumIsX64ProcessElf(h)); // x86 32-bit, not supported
 h[18]=62; h[19]=1; assert(!SandiumIsX64ProcessElf(h));
 h[19]=0; h[4]=1; assert(!SandiumIsX64ProcessElf(h));
 h[4]=2; h[5]=2; assert(!SandiumIsX64ProcessElf(h));
 h[5]=1; h[0]=0; assert(!SandiumIsX64ProcessElf(h));
#if defined(ARCH_CPU_ARM64) && defined(__x86_64__)
 assert(SandiumIsArm64LibraryInX64Process());
#else
 assert(!SandiumIsArm64LibraryInX64Process());
#endif
}
'''
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'guard.cc';p.write_text('#include <array>\n#include <cstdio>\n'+guard.HELPER+main)
            for flags in ([],['-DARCH_CPU_ARM64']):
                subprocess.run([compiler,'-std=c++17','-Wall','-Wextra','-Werror',*flags,str(p),'-o',str(p.with_suffix(''))],check=True)
                subprocess.run([str(p.with_suffix(''))],check=True)

if __name__=='__main__':unittest.main()
