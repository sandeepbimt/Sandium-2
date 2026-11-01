# Sandium Brave ARM64 distribution and APK size plan

## Why the 595 MB APK is likely oversized

The previous CI output was `BraveMonoarm64.apk` from Brave Core `v1.98.62`.

In that exact Brave Core version, `build/commands/lib/buildArgs.ts` sets
`enable_android_secondary_abi = true` for CI builds when all of the following
are true:

- Android target architecture is `arm64` or `x64`;
- output format is `apk`; and
- `is_official_build` is false.

This is a CI override intended to place both 32-bit and 64-bit native libraries
in the APK. The current build passes `enable_android_secondary_abi:false`,
but the Brave build helper's CI rule can override that value for APK output.
This is the leading explanation for the large APK; the automated ZIP inventory
must confirm the exact ABI payload in the downloaded artifact.

Brave's Android installation guidance says modern ARM64 devices should use
`Bravearm64Universal.apk`. It describes `BraveMonoarm64.apk` as containing
both 32-bit and 64-bit libraries.

## New distribution target

The experimental configuration switches the build graph to:

- `--target_android_output_format=aab`
- `--android_aab_to_apk`
- `--target create_dist`
- `--target_arch=arm64`
- `--gn enable_android_secondary_abi:false`

For Brave Core `v1.98.62`, the source defines:

- AAB intermediate: `apks/BraveMonoarm64.aab`
- Device-test APK: `apks/Bravearm64Universal.apk`

The root `create_dist` target depends on
`build/android:sign_app_convert_aab_to_apk` when
`android_aab_to_apk=true` and `target_cpu=arm64`. That action converts the
AAB to Brave's ARM64 universal APK.

The pipeline publishes both artifacts:

- `Sandium-Brave-arm64.apk`: direct installation/testing on ARM64 devices.
- `Sandium-Brave-arm64.aab`: bundle artifact for further Play distribution
  preparation and validation.

## Important release qualification

This experimental branch intentionally keeps the current non-official
development configuration:

- `is_official_build=false`
- `brave_channel=development`
- package ID `com.brave.browser_default`

Therefore, the AAB is an internal/test bundle, not yet a production Play
release. Brave's official Android builds require additional release
configuration and signing credentials. Do not change to
`is_official_build=true` until the required Brave release values and Android
keystore credentials are configured and verified.

## Size audit

`.circleci/scripts/analyze-brave-apk-size.py` inspects APK/AAB ZIP entries
without extracting them. It reports:

- actual file size and aggregate ZIP entry sizes;
- ABI directories and their compressed/uncompressed native-library sizes;
- ELF machine types found in native libraries;
- largest package entries;
- symbol-named files found by filename.

The CircleCI artifact directory includes `apk-size-report.txt` and
`aab-size-report.txt` for the next experimental build. The audit does not
claim to detect embedded ELF debug sections; that requires a separate ELF
section-table scan.

## Workflow controls

The experimental full build is named `BRAVE-FULL` and every stage name starts
with `BRAVE-FULL`. The current branch filters intentionally still point only
to `sandium/brave-android-poc`, so this experiment branch does not
automatically trigger the expensive CircleCI workflow.

The existing working branch is not modified by this experiment. Review the
new branch and its static checks before enabling the workflow. A separate
`BRAVE-FAST` workflow remains a later task after the full distribution path
is validated.

## Acceptance criteria

1. The APK audit reports only `arm64-v8a` for the universal APK.
2. APK ZIP integrity, APK signature, and package ID are valid.
3. AAB ZIP integrity, JAR signature, and bundletool validation are valid.
4. Both artifacts are saved and downloadable from CircleCI.
5. The action ledger uses `create_dist` consistently for dry-run, actual
   compilation and reconciliation.
6. Stage duration remains 30 minutes per stage, maximum five stages.
7. Completion and fast-exit markers require both validated artifacts.
