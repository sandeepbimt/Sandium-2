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
        src=(ROOT/'tests/fixtures/translation-guard/jni_android.cc').read_text()
        out=guard.transform(src)
        self.assertEqual(guard.transform(out),out)
        self.assertEqual(out.count(guard.FUNCTION_NEW),1)
        self.assertLess(out.index(guard.FUNCTION_NEW), out.index('g_previous_functions = env->functions;'))
        self.assertIn('std::fclose(maps)',out)
        self.assertNotIn('ro.product.cpu',out)
        self.assertIn('void UnhookJniFindClassForTesting',out)

    def test_previous_checkpoint_migrates_exactly_to_safe_parser(self):
        src=(ROOT/'tests/fixtures/translation-guard/jni_android.cc').read_text()
        current=guard.transform(src)
        previous=current.replace(guard.HELPER,guard.PREVIOUS_MAPPED_HELPER).replace('#include <charconv>\n#include <string_view>\n','')
        self.assertEqual(guard.transform(previous),current)
        self.assertNotIn('sscanf',current)
        self.assertNotIn('UNSAFE_BUFFERS',current)
        with self.assertRaises(ValueError):
            guard.transform(previous.replace('%lx-%lx','%lx:%lx'))

    def test_unknown_source_and_partial_guard_rejected(self):
        with self.assertRaises(ValueError):guard.transform('unrecognized')
        with self.assertRaises(ValueError):guard.transform(guard.MARKER)

    def test_legacy_guard_removed_and_both_callers_preserved(self):
        source=(ROOT/'tests/fixtures/translation-guard/library_loader_hooks.cc').read_text()
        legacy=source.replace('#include <string>\n', '#include <string>\n\n'+guard.HEADERS).replace('base::AtExitManager* g_at_exit_manager',guard.LEGACY_HELPER+'base::AtExitManager* g_at_exit_manager').replace(guard.OLD,guard.NEW)
        self.assertEqual(guard.restore_legacy(legacy),source)
        self.assertEqual(guard.restore_legacy(source),source)
        self.assertIn('HookJniFindClass(env);',source)
        cardboard=(ROOT/'tests/fixtures/translation-guard/cardboard_sdk_impl.cc').read_text()
        self.assertIn('HookJniFindClass(AttachCurrentThread());',cardboard)
        with self.assertRaises(ValueError):guard.restore_legacy(guard.MARKER)

    def test_function_guard_precedes_all_table_access(self):
        src=(ROOT/'tests/fixtures/translation-guard/jni_android.cc').read_text()
        patched=guard.transform(src)
        fn=patched.split('void HookJniFindClass(JNIEnv* env) {',1)[1].split('void Unhook',1)[0]
        self.assertLess(fn.index('SandiumIsArm64LibraryInX64Process(env)'),fn.index('if (g_previous_functions)'))
        self.assertEqual(fn.count('env->functions = &g_hooked_functions;'),1)

    def test_compiled_function_both_call_paths_and_native_fallback(self):
        compiler=shutil.which('clang++') or shutil.which('g++')
        src=(ROOT/'tests/fixtures/translation-guard/jni_android.cc').read_text()
        fn=guard.transform(src).split('void HookJniFindClass(JNIEnv* env) {',1)[1].split('void UnhookJniFindClassForTesting',1)[0]
        code=r'''
#include <cassert>
#include <iostream>
#define BUILDFLAG(x) 0
#define LOG(x) std::cerr
struct JNINativeInterface { void (*FindClass)(); };
struct JNIEnv { const JNINativeInterface* functions; };
const JNINativeInterface* g_previous_functions=nullptr;
JNINativeInterface g_hooked_functions{};
void FindClassHook() {}
void Original() {}
bool translated=false;
bool SandiumIsArm64LibraryInX64Process(JNIEnv*) { return translated; }
'''+'void HookJniFindClass(JNIEnv* env) {'+fn+r'''
void Loader(JNIEnv* e) { HookJniFindClass(e); }
void Cardboard(JNIEnv* e) { HookJniFindClass(e); }
int main() {
 JNINativeInterface original{Original};
 for (auto caller : {Loader, Cardboard}) {
   for (bool cross_isa : {false,true}) {
     translated=cross_isa; g_previous_functions=nullptr;
     JNIEnv e{&original}; caller(&e); caller(&e);
     if(cross_isa) { assert(e.functions==&original); assert(!g_previous_functions); }
     else { assert(e.functions==&g_hooked_functions); assert(g_previous_functions==&original); assert(e.functions->FindClass==FindClassHook); }
   }
 }
}
'''
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'hook.cc';p.write_text(code)
            subprocess.run([compiler,'-std=c++17','-Wall','-Wextra','-Werror',str(p),'-o',str(p.with_suffix(''))],check=True)
            subprocess.run([str(p.with_suffix(''))],check=True,capture_output=True)

    def test_native_detector_cxx_matrix(self):
        compiler=shutil.which('clang++') or shutil.which('g++')
        self.assertIsNotNone(compiler,'A C++ compiler is required for guard verification')
        main=r'''
#include <cassert>
#include <cstring>
bool mapped(std::array<unsigned char,20>& h, unsigned long inode=9,
            unsigned int minor=2, const char* perms="r--p", unsigned long off=0) {
 FILE* maps=std::tmpfile(); assert(maps);
 auto addr=reinterpret_cast<unsigned long>(h.data());
 std::fprintf(maps,"1000-2000 r--p 1000 01:02 9 /host.so\n");
 std::fprintf(maps,"%lx-%lx %s %lx 01:%02x %lu /host.so\n",addr,addr+20,perms,off,minor,inode);
 std::rewind(maps); bool result=SandiumJniTargetIsMappedX64(maps,0x1234);
 std::fclose(maps);return result;
}
int main() {
 std::array<unsigned char,20> h{};
 h[0]=0x7f; h[1]='E'; h[2]='L'; h[3]='F'; h[4]=2; h[5]=1; h[6]=1; h[18]=62;
 unsigned long begin=0,end=0,offset=0,inode=0; unsigned int major=0,minor=0;
 std::string_view permissions;
 auto parse=[&](std::string_view line) { return SandiumParseMapLine(line,begin,end,permissions,offset,major,minor,inode); };
 assert(parse("1000-2000 r-xp 0000 00:ff 123 /with spaces.so"));
 assert(begin==0x1000 && end==0x2000 && offset==0 && major==0 && minor==255 && inode==123 && permissions=="r-xp");
 for (auto bad : {"", "1000-2000 r-xp", "2000-1000 r-xp 0 1:2 9", "1000-2000 r-xp 0 1:2 -9", "1000-2000 r-xp 0 1:2 9junk", "1000-2000 r-xp 0 1:2 99999999999999999999999999", "1000-2000 r-xp 0 fffffffffffffffff:2 9", "1000-2000 r-xp xyz 1:2 9", "1000-2000 r-xp 0 1:2:3 9"}) assert(!parse(bad));
 assert(SandiumIsX64ProcessElf(h));
 assert(mapped(h));
 assert(!mapped(h,10)); assert(!mapped(h,9,3));
 assert(!mapped(h,9,2,"---p")); assert(!mapped(h,9,2,"r--p",0x1000));
 h[18]=183; assert(!SandiumIsX64ProcessElf(h)); assert(!mapped(h)); // real ARM64 VM
 h[18]=3; assert(!SandiumIsX64ProcessElf(h)); // x86 32-bit, not supported
 h[18]=62; h[19]=1; assert(!SandiumIsX64ProcessElf(h));
 h[19]=0; h[4]=1; assert(!SandiumIsX64ProcessElf(h));
 h[4]=2; h[5]=2; assert(!SandiumIsX64ProcessElf(h));
 h[5]=1; h[0]=0; assert(!SandiumIsX64ProcessElf(h));
#if defined(ARCH_CPU_ARM64) && defined(__x86_64__)
 assert(!SandiumIsArm64LibraryInX64Process(nullptr));
#else
 assert(!SandiumIsArm64LibraryInX64Process(nullptr));
#endif
}
'''
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'guard.cc';p.write_text('#include <array>\n#include <cstdio>\n#include <cstring>\n#include <cstdint>\n#include <charconv>\n#include <string_view>\nstruct JNINativeInterface { void (*FindClass)(); }; struct JNIEnv { const JNINativeInterface* functions; };\n'+guard.HELPER+main)
            for flags in ([],['-DARCH_CPU_ARM64']):
                subprocess.run([compiler,'-std=c++17','-Wall','-Wextra','-Werror',*flags,str(p),'-o',str(p.with_suffix(''))],check=True)
                subprocess.run([str(p.with_suffix(''))],check=True)

if __name__=='__main__':unittest.main()
