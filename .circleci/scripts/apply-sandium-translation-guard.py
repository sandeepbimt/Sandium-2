#!/usr/bin/env python3
"""Isolated emulator test only: do not install guest JNI pointer in host JNI table."""
import argparse
from pathlib import Path

REL = 'base/android/jni_android.cc'
LEGACY_REL = 'base/android/library_loader/library_loader_hooks.cc'
MARKER = '// SANDIUM_TRANSLATION_ONLY_JNI_GUARD'
HEADERS = '''#include <array>
#include <cstdio>

#include "build/build_config.h"
#include "base/logging.h"
'''
LEGACY_HELPER = '''// SANDIUM_TRANSLATION_ONLY_JNI_GUARD
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
HELPER = '''// SANDIUM_TRANSLATION_ONLY_JNI_GUARD
// The native bridge rewrites /proc/self/exe and guest dladdr cannot resolve
// host libart. Inspect the original JNI target's mapped ELF, not ABI properties.
[[maybe_unused]] bool SandiumIsX64ProcessElf(const std::array<unsigned char, 20>& header) {
  return header[0] == 0x7f && header[1] == 'E' && header[2] == 'L' &&
         header[3] == 'F' && header[4] == 2 && header[5] == 1 &&
         header[6] == 1 && header[18] == 62 && header[19] == 0;
}

[[maybe_unused]] bool SandiumJniTargetIsMappedX64(FILE* maps, uintptr_t target) {
  char line[2048];
  unsigned long begin = 0, end = 0, offset = 0, inode = 0;
  unsigned int major = 0, minor = 0;
  char permissions[5]{};
  unsigned long owner_inode = 0;
  unsigned int owner_major = 0, owner_minor = 0;
  while (std::fgets(line, sizeof(line), maps)) {
    if (std::sscanf(line, "%lx-%lx %4s %lx %x:%x %lu", &begin, &end,
                    permissions, &offset, &major, &minor, &inode) != 7) continue;
    if (target >= begin && target < end && inode != 0) {
      owner_inode = inode; owner_major = major; owner_minor = minor;
      break;
    }
  }
  if (!owner_inode) return false;
  std::rewind(maps);
  while (std::fgets(line, sizeof(line), maps)) {
    if (std::sscanf(line, "%lx-%lx %4s %lx %x:%x %lu", &begin, &end,
                    permissions, &offset, &major, &minor, &inode) != 7) continue;
    if (inode != owner_inode || major != owner_major || minor != owner_minor ||
        offset != 0 || permissions[0] != 'r' || end < begin || end - begin < 20)
      continue;
    std::array<unsigned char, 20> header{};
    std::memcpy(header.data(), reinterpret_cast<const void*>(begin), header.size());
    return SandiumIsX64ProcessElf(header);
  }
  return false;
}

bool SandiumIsArm64LibraryInX64Process([[maybe_unused]] JNIEnv* env) {
#if defined(ARCH_CPU_ARM64)
  if (!env || !env->functions || !env->functions->FindClass) return false;
  FILE* maps = std::fopen("/proc/self/maps", "r");
  if (!maps) return false;
  const bool host_x64 = SandiumJniTargetIsMappedX64(
      maps, reinterpret_cast<uintptr_t>(env->functions->FindClass));
  std::fclose(maps);
  return host_x64;
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

FUNCTION_OLD = 'void HookJniFindClass(JNIEnv* env) {\n#if !BUILDFLAG(IS_ROBOLECTRIC)\n'
FUNCTION_NEW = FUNCTION_OLD + '''  // Guard every caller, including Cardboard initialization before LibraryLoaded.
  if (SandiumIsArm64LibraryInX64Process(env)) {
    LOG(WARNING) << "Sandium emulator test: skipped cross-ISA JNI FindClass hook";
    return;
  }
'''

def transform(source):
    if MARKER in source:
        if source.count(HELPER) != 1 or source.count(FUNCTION_NEW) != 1:
            raise ValueError('Partial or unexpected function-level translation guard')
        return source
    if source.count('#include <stddef.h>\n') != 1 or source.count(FUNCTION_OLD) != 1:
        raise ValueError('Pinned JNI implementation shape changed')
    anchor = 'namespace {\n'
    if source.count(anchor) != 1:
        raise ValueError('Pinned namespace anchor changed')
    return source.replace('#include <stddef.h>\n', '#include <stddef.h>\n#include <array>\n#include <cstdio>\n#include <cstdint>\n#include <cstring>\n').replace(
        anchor, anchor+'\n'+HELPER).replace(FUNCTION_OLD, FUNCTION_NEW)

def restore_legacy(source):
    if MARKER not in source:
        return source
    if source.count(LEGACY_HELPER) != 1 or source.count(NEW) != 1 or source.count(HEADERS) != 1:
        raise ValueError('Partial or unexpected legacy caller guard')
    return source.replace('#include <string>\n\n'+HEADERS, '#include <string>\n').replace(LEGACY_HELPER, '').replace(NEW, OLD)

def main():
    p=argparse.ArgumentParser();p.add_argument('source_root',type=Path);a=p.parse_args()
    target=a.source_root/REL
    source=target.read_text();out=transform(source)
    legacy=a.source_root/LEGACY_REL
    legacy_source=legacy.read_text()
    restored=restore_legacy(legacy_source)
    target.write_text(out)
    legacy.write_text(restored)
    print('SANDIUM_TRANSLATION_GUARD=APPLIED all-callers test-only; native ARM hook unchanged')
if __name__=='__main__':main()
