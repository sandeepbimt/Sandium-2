#!/usr/bin/env python3
"""Isolated emulator test only: do not install guest JNI pointer in host JNI table."""
import argparse
from pathlib import Path

REL = 'base/android/library_loader/library_loader_hooks.cc'
MARKER = '// SANDIUM_TRANSLATION_ONLY_JNI_GUARD'
HEADERS = '''#include <array>
#include <cstdio>

#include "build/build_config.h"
#include "base/logging.h"
'''
HELPER = '''// SANDIUM_TRANSLATION_ONLY_JNI_GUARD
// A translated ARM64 library can share the native x86_64 VM's JNIEnv table.
// A raw ARM function pointer in that table cannot be called by host JNI code.
// Read the kernel's executable identity, not app ABI properties which bridges
// may rewrite. Unknown/read-failure cases retain upstream behavior.
[[maybe_unused]] bool SandiumIsX64ProcessElf(const std::array<unsigned char, 20>& header) {
  return header[0] == 0x7f && header[1] == 'E' && header[2] == 'L' &&
         header[3] == 'F' && header[4] == 2 && header[5] == 1 &&
         header[6] == 1 && header[18] == 62 && header[19] == 0;
}

bool SandiumIsArm64LibraryInX64Process() {
#if defined(ARCH_CPU_ARM64)
  std::array<unsigned char, 20> header{};
  FILE* executable = std::fopen("/proc/self/exe", "rb");
  if (!executable) return false;
  const size_t size = std::fread(header.data(), 1, header.size(), executable);
  std::fclose(executable);
  return size == header.size() && SandiumIsX64ProcessElf(header);
#else
  return false;
#endif
}

'''
OLD = '    HookJniFindClass(env);'
NEW = '''    if (!SandiumIsArm64LibraryInX64Process()) {
      HookJniFindClass(env);
    } else {
      LOG(WARNING) << "Sandium emulator test: skipped cross-ISA JNI FindClass hook";
    }'''

def transform(source):
    if MARKER in source:
        if source.count(HELPER) != 1 or source.count(NEW) != 1:
            raise ValueError('Partial or unexpected translation guard')
        return source
    if source.count('#include <string>\n') != 1 or source.count(OLD) != 1:
        raise ValueError('Pinned library loader shape changed')
    if source.count('base::AtExitManager* g_at_exit_manager') != 1:
        raise ValueError('Pinned namespace anchor changed')
    return source.replace('#include <string>\n', '#include <string>\n\n'+HEADERS).replace(
        'base::AtExitManager* g_at_exit_manager', HELPER+'base::AtExitManager* g_at_exit_manager').replace(OLD, NEW)

def main():
    p=argparse.ArgumentParser();p.add_argument('source_root',type=Path);a=p.parse_args()
    target=a.source_root/REL
    source=target.read_text();out=transform(source)
    target.write_text(out)
    print('SANDIUM_TRANSLATION_GUARD=APPLIED test-only; native ARM hook unchanged')
if __name__=='__main__':main()
