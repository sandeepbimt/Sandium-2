# Chromium158 host preparation evidence

All source fixtures fetched at Chromium52bdd21723d5db0c9ab11716d38feac74828cf84 and verified against its exact Git tree blob IDs; manifest records SHA256 and Gitblob identity.

Native `install-build-deps.py` supports `--android` (deprecated but functional lib32 alias), `--no-prompt`, `--quick-check`, and optional dependency exclusions. Quick-check exits before `check_root`, apt update/install, font or locale changes. Preparation uses native installer if that read-only check fails. Native installer updates the apt package index and installs its selected missing/upgraded packages; it does not invoke a full apt upgrade. Android/lib32 enables i386 architecture through native installer. No unsupported-distro bypass is selected.

JDK is DEPS-owned `third_party/jdk/current`, pinned `version:2@jdk-25.0.5+8.a4d27635bd.cr0`. Public SDK DEPS/config pin platform37.2 and build-tools37.0.0. Native aapt2 path is specified by config.gni. The helper never downloads a substitute SDK/JDK or uses system JAVA_HOME as proof.

`host_deps.py prepare|verify --root PROJECT` executes inside caller's deadline/process group, without new sessions or detached children. No success marker substitutes for native package and executable capability verification. Preparation is an explicit mutating call; verify never invokes sudo/installation. Missing source-synced SDK/JDK fails rather than silently claiming build-ready. Source-only checkpoints do not need to call this helper.

Host unit tests mock all installation commands. No package install was executed during this development task. Fresh-machine native preparation and full compile remain integration checks.

## Brave composition correction

The live synchronized checkout is not raw Chromium. Exact Brave bd6d26d patches
`patches/DEPS.patch` and `patches/build-config-android-config.gni.patch` are authenticated and replayed in tests against raw inputs. Only their exact postimages are accepted live. DEPS disables the Mac toolchain hook; config imports Brave's Android config. The exact imported Brave config is retained here for audit and does not assign SDK/JDK versions (its legitimate product removal edits are owned by the product adapter, not this host verifier).

Effective versions are derived from these authenticated composed DEPS/config bytes: JDK25.0.5, SDK platform37.2, build-tools37.0.0. Tests reject raw DEPS and arbitrary drift; this correction does not broadly accept modified source.
