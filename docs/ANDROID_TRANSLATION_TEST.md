# Isolated ARM64-on-x64 emulator test

This branch is an experiment, not a phone release. Keep its APK and test results
separate from normal artifacts until a translated launch is actually verified.

## Observed baseline

The exact ARM64 APK from CircleCI #1225 installs on official Android 15 Google
APIs x86_64 with its native bridge. Three launch attempts faulted at the same raw
ARM64 Chromium `FindClassHook` address called from host x86_64 `libjavacore`.
The disassembled hook installer matches Chromium's JNI table replacement.
This is strong translation-incompatibility evidence; the patched A/B launch is
still required to establish that this guard resolves the failure.

## Scope

The common `HookJniFindClass(JNIEnv*)` entry point is guarded, covering both
LibraryLoader and Cardboard initialization. Both original callers are unchanged.
The guard applies only to an ARM64 compilation whose original JNI FindClass
pointer belongs to a mapped ELF64 little-endian x86_64 object. It finds the
pointer's owning `/proc/self/maps` range, then its readable offset-zero mapping
with matching device and inode, and reads the in-memory ELF header. This avoids
both translated `/proc/self/exe` and guest `dladdr` identity limitations.

Native ARM64 JNI targets retain the hook. Native x64 builds retain the hook.
Missing maps, unknown/unmapped targets, anonymous mappings, unreadable headers,
and unknown ELF machines retain upstream behavior. No sandbox, SELinux,
renderer isolation, general JNI registration or security setting changes.

The upstream hook supports Cardboard SDK class lookup in Chrome splits. That
VR compatibility workaround is skipped only for the confirmed cross-ISA case;
VR functionality must not be claimed validated. A warning records each skip.
The old caller-only patch is strictly recognized and removed if restored from
an earlier experiment checkpoint. Partial or unexpected patches fail closed.

## Verification limits

Host C++ tests compile the detector for ARM64-guard-enabled and normal
branches and validate ELF variants, map device/inode matching, readability, and
offset restrictions. Compiled function tests cover both caller paths and native
fallback without mutating the JNI table on the translated path. Pinned-source patch shape and idempotence
are tested. These tests do not emulate the bridge. On the runner, require:

1. Exact APK SHA, ABI and source revision recorded.
2. Android 15 boot and KVM verified; real UI launch survives three attempts.
3. Skip warning present; crash buffer checked, not merely install success.
4. Cold/warm navigation and real edge gesture completion/cancellation captured.

An x64-native APK remains the fallback if other ARM translation incompatibilities
appear. Graphics use SwiftShader, so timing/FPS are not Oppo performance claims.

## #1242 failure analysis (2026-11-16)

The exact APK SHA256 is
`35f4ad516b3a82f709494add76bff1df7beb8e87439a9a82f7cbcd6fa6cf6737`.
Its libchrome SHA256 is
`1fac194744fee0bb3cea2de12328a9b925d698cf4968dc76bf6e47e89e7db627`.
The guard warning exists in this binary and is absent from #1233. Disassembly
shows the actual ELF fread/check branch at 0xcf6ec2c–0xcf6ecc4, leading to
HookJniFindClass at 0xcf6eccc. This rules out an entirely stale guard library.

There is a second, unguarded call at 0x11e0e334. Its initialized_ gate,
AttachCurrentThread, HookJniFindClass, GetVM, Cardboard_initializeAndroid sequence
matches pinned Chromium 156.0.8078.74
`device/vr/android/cardboard/cardboard_sdk_impl.cc::CardboardSdkImpl::Initialize`.
The experiment must guard the common HookJniFindClass function, not one caller.
Both upstream callers are retained unchanged.

A minimal ARM64 JNI probe on the actual API35 emulator also disproved the
original detector assumption: the bridge resolves /proc/self/exe as
/system/bin/arm64/app_process64, ELF machine183. The kernel-identity claim above
was therefore not true from translated code. A replacement detector must be
probed before claiming the experiment works. Native ARM must retain upstream
hook behavior, and unknown cases must retain it as well.

### Replacement detector runtime proof

Free Android15 API35 x86_64 KVM runner probe43951639082 used an ARM64 JNI
library. FindClass target0x7d581ac8b3f0 belonged to host libart range
7d581a800000–7d581afb4000, offset0x200000, devicefe:2d/inode53. The same
file's readable offset-zero mapping7d581a600000–7d581a750000 contained
ELF magic7f454c46, class2, endian1, machine62. The file header agreed.
The original exe detector simultaneously returned machine183. Guest dladdr
failed to resolve the native target, so it is not used. Target mappings are
r--p in this translated view; requiring executable permission would reject the
verified case. The mapped ELF detector is verified, not the full Sandium
patched launch: that still requires the next APK A/B test.
