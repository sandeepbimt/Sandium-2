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

Only the existing browser-main-thread `HookJniFindClass(env)` invocation is
conditional. The guest library must be compiled ARM64 AND the process executable
(`/proc/self/exe`, the kernel-resolved native app_process executable) must contain
an ELF64 little-endian header with EM_X86_64. Android ABI properties and uname
are not used, since a native bridge can adapt guest-visible identity.

Native ARM64 processes retain the hook. Native x64 builds retain the hook. Read
failures, truncated ELF headers and unknown machines retain the hook. No sandbox,
SELinux, renderer isolation, general JNI registration or security check changes.

The upstream hook is for Cardboard SDK lookup of classes in the Chrome split.
That VR class-loader compatibility workaround is absent only in this confirmed
cross-ISA case; VR functionality must not be claimed validated by this test.
A warning records the skip. Native browser features are otherwise unchanged by
this patch, but this statement is source scope, not runtime proof.

## Verification limits

Host C++ tests compile the actual detector for ARM64-guard-enabled and normal
branches and validate ELF variants. Pinned-source patch shape and idempotence
are tested. These tests do not emulate the bridge. On the runner, require:

1. Exact APK SHA, ABI and source revision recorded.
2. Android 15 boot and KVM verified; real UI launch survives three attempts.
3. Skip warning present; crash buffer checked, not merely install success.
4. Cold/warm navigation and real edge gesture completion/cancellation captured.

An x64-native APK remains the fallback if other ARM translation incompatibilities
appear. Graphics use SwiftShader, so timing/FPS are not Oppo performance claims.
