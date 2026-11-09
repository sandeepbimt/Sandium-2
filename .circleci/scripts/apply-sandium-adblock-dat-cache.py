#!/usr/bin/env python3
"""Install a first-launch, native Brave DAT fallback for Sandium Android."""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

EXPECTED_CORE_TAG = "v1.98.62"
EXPECTED_CORE_SHA = "44a84b1f89d9a35287289d6a3d493e362f5a5123"
ASSET_PATH = "assets/sandium/adblock/engine1.dat"
DAT_OUT_PATH = "$root_out_dir/gen/sandium_adblock/engine1.dat"


def replace_once(source: str, old: str, new: str, marker: str, label: str) -> str:
    if marker in source:
        if new not in source:
            raise RuntimeError(f"{label}: marker exists but replacement differs")
        return source
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one source anchor, found {count}")
    updated = source.replace(old, new, 1)
    if marker not in updated:
        raise RuntimeError(f"{label}: replacement marker missing")
    return updated


def read(path: Path) -> str:
    if not path.is_file():
        raise RuntimeError(f"missing pinned Brave source file: {path}")
    return path.read_text(encoding="utf-8")


def write(path: Path, before: str, after: str, label: str) -> None:
    if after != before:
        path.write_text(after, encoding="utf-8")
    if read(path) != after:
        raise RuntimeError(f"{label}: post-write verification failed")
    print(f"SANDIUM_ADBLOCK_DAT_PATCH={label}:PASS")


def transform_cache_header(source: str) -> str:
    old = (
        "  void MaybeReadCachedDATFiles(\n"
        "      base::OnceCallback<void(std::optional<DATFileDataBuffer>,\n"
        "                              std::optional<DATFileDataBuffer>)> on_complete);\n"
    )
    new = old + (
        "\n"
        "  // Reads Sandium's immutable additional-engine DAT from the APK.\n"
        "  // The caller persists it only after the native engine accepts it.\n"
        "  void MaybeReadBundledAdditionalDATFile(\n"
        "      base::OnceCallback<void(std::optional<DATFileDataBuffer>)> on_complete);\n"
    )
    return replace_once(source, old, new,
                        "void MaybeReadBundledAdditionalDATFile(",
                        "cache-manager-bundled-read-api")


def transform_cache_cc(source: str) -> str:
    source = replace_once(
        source,
        '#include "base/files/file_path.h"\n',
        '#include "base/files/file_path.h"\n'
        '#include "build/build_config.h"\n'
        '#if BUILDFLAG(IS_ANDROID)\n'
        '#include "base/android/apk_assets.h"\n'
        '#include "base/files/file.h"\n'
        '#include "base/files/memory_mapped_file.h"\n'
        '#endif\n',
        '#include "base/android/apk_assets.h"',
        "cache-manager-android-asset-includes",
    )
    old = (
        "  return std::make_pair(base::ReadFileToBytes(default_engine_dat_file),\n"
        "                        base::ReadFileToBytes(additional_engine_dat_file));\n"
        "}\n\n"
        "}  // namespace\n"
    )
    new = (
        "  return std::make_pair(base::ReadFileToBytes(default_engine_dat_file),\n"
        "                        base::ReadFileToBytes(additional_engine_dat_file));\n"
        "}\n\n"
        "std::optional<DATFileDataBuffer> ReadBundledAdditionalDATFile() {\n"
        "#if BUILDFLAG(IS_ANDROID)\n"
        "  base::MemoryMappedFile::Region region =\n"
        "      base::MemoryMappedFile::Region::kWholeFile;\n"
        f'  const int asset_fd = base::android::OpenApkAsset("{ASSET_PATH}", &region);\n'
        "  if (asset_fd < 0) {\n"
        "    return std::nullopt;\n"
        "  }\n"
        "  base::File asset_file(asset_fd);\n"
        "  if (!asset_file.IsValid() || region.size == 0) {\n"
        "    return std::nullopt;\n"
        "  }\n"
        "  base::MemoryMappedFile mapped_asset;\n"
        "  if (!mapped_asset.Initialize(std::move(asset_file), region) ||\n"
        "      mapped_asset.length() == 0) {\n"
        "    return std::nullopt;\n"
        "  }\n"
        "  const auto bytes = mapped_asset.bytes();\n"
        "  return DATFileDataBuffer(bytes.begin(), bytes.end());\n"
        "#else\n"
        "  return std::nullopt;\n"
        "#endif\n"
        "}\n\n"
        "}  // namespace\n"
    )
    source = replace_once(source, old, new,
                          "ReadBundledAdditionalDATFile() {",
                          "cache-manager-asset-reader")

    old = (
        "void AdBlockDATCacheManager::MaybeReadCachedDATFiles(\n"
        "    base::OnceCallback<void(std::optional<DATFileDataBuffer>,\n"
        "                            std::optional<DATFileDataBuffer>)> on_complete) {\n"
        "  CHECK(base::FeatureList::IsEnabled(features::kAdblockDATCache));\n"
        "  task_runner_->PostTaskAndReplyWithResult(\n"
        "      FROM_HERE, base::BindOnce(&ReadCachedDATFilesFromDisk, cache_dir_),\n"
        "      base::BindOnce(\n"
        "          [](base::OnceCallback<void(std::optional<DATFileDataBuffer>,\n"
        "                                     std::optional<DATFileDataBuffer>)>\n"
        "                 callback,\n"
        "             std::pair<std::optional<DATFileDataBuffer>,\n"
        "                       std::optional<DATFileDataBuffer>> result) {\n"
        "            std::move(callback).Run(std::move(result.first),\n"
        "                                    std::move(result.second));\n"
        "          },\n"
        "          std::move(on_complete)));\n"
        "}\n"
    )
    new = old + (
        "\n"
        "void AdBlockDATCacheManager::MaybeReadBundledAdditionalDATFile(\n"
        "    base::OnceCallback<void(std::optional<DATFileDataBuffer>)> on_complete) {\n"
        "  task_runner_->PostTaskAndReplyWithResult(\n"
        "      FROM_HERE, base::BindOnce(&ReadBundledAdditionalDATFile),\n"
        "      std::move(on_complete));\n"
        "}\n"
    )
    return replace_once(source, old, new,
                        "void AdBlockDATCacheManager::MaybeReadBundledAdditionalDATFile(",
                        "cache-manager-async-bundled-read")


def transform_service_header(source: str) -> str:
    old = (
        "  void OnReadCachedDATFiles(std::optional<DATFileDataBuffer> default_dat,\n"
        "                            std::optional<DATFileDataBuffer> additional_dat);\n"
    )
    new = old + (
        "  void OnReadBundledAdditionalDATFile(\n"
        "      std::optional<DATFileDataBuffer> dat);\n"
    )
    source = replace_once(source, old, new,
                          "void OnReadBundledAdditionalDATFile(",
                          "service-bundled-read-callback")

    old = (
        "  bool default_filter_list_loaded_for_testing_ = false;\n"
        "  bool additional_filter_list_loaded_for_testing_ = false;\n\n"
        "  SEQUENCE_CHECKER(sequence_checker_);\n"
    )
    new = (
        "  bool default_filter_list_loaded_for_testing_ = false;\n"
        "  bool additional_filter_list_loaded_for_testing_ = false;\n\n"
        "  // A packaged DAT is tried once only after the profile DAT is absent or\n"
        "  // rejected. It never replaces a DAT that the native engine accepted.\n"
        "  bool bundled_additional_dat_attempted_ = false;\n"
        "  std::optional<DATFileDataBuffer> bundled_additional_dat_pending_write_;\n\n"
        "  SEQUENCE_CHECKER(sequence_checker_);\n"
    )
    return replace_once(source, old, new,
                        "bool bundled_additional_dat_attempted_ = false;",
                        "service-bundled-dat-state")


def transform_service_cc(source: str) -> str:
    old = (
        "void AdBlockService::OnDATLoaded(bool is_default_engine, bool success) {\n"
        "  DCHECK_CALLED_ON_VALID_SEQUENCE(sequence_checker_);\n"
        "  if (is_default_engine) {\n"
        "    default_dat_loaded_for_testing_ = true;\n"
        "  } else {\n"
        "    additional_dat_loaded_for_testing_ = true;\n"
        "  }\n"
        "  // If the cached DAT failed to load, fall back to loading from filter lists.\n"
        "  if (!success) {\n"
        "    if (is_default_engine) {\n"
        "      filters_provider_manager_->ForceNotifyObserver(*default_service_observer_,\n"
        "                                                     true);\n"
        "    } else {\n"
        "      filters_provider_manager_->ForceNotifyObserver(\n"
        "          *additional_filters_service_observer_, false);\n"
        "    }\n"
        "  }\n"
        "  observers_.Notify(&Observer::OnDATLoaded, is_default_engine, success);\n"
        "}\n"
    )
    new = (
        "void AdBlockService::OnDATLoaded(bool is_default_engine, bool success) {\n"
        "  DCHECK_CALLED_ON_VALID_SEQUENCE(sequence_checker_);\n"
        "  if (is_default_engine) {\n"
        "    default_dat_loaded_for_testing_ = true;\n"
        "  } else if (success || bundled_additional_dat_attempted_) {\n"
        "    // Do not signal completion while the one-time APK fallback is pending.\n"
        "    additional_dat_loaded_for_testing_ = true;\n"
        "  }\n\n"
        "  // Do not rebuild subscriptions while the packaged baseline is being\n"
        "  // read. This path is reached only after the profile cache missed or\n"
        "  // failed native deserialization; a valid user cache never reaches it.\n"
        "  if (!success && !is_default_engine &&\n"
        "      !bundled_additional_dat_attempted_) {\n"
        "    bundled_additional_dat_attempted_ = true;\n"
        "    dat_cache_manager_->MaybeReadBundledAdditionalDATFile(\n"
        "        base::BindOnce(&AdBlockService::OnReadBundledAdditionalDATFile,\n"
        "                       weak_factory_.GetWeakPtr()));\n"
        "    return;\n"
        "  }\n\n"
        "  // Cache the packaged engine only after LoadDAT has confirmed that the\n"
        "  // pinned native runtime can deserialize it. Never overwrite a good\n"
        "  // profile DAT or replace it merely because an APK asset exists.\n"
        "  bool loaded_bundled_additional_dat = false;\n"
        "  if (!is_default_engine && bundled_additional_dat_pending_write_) {\n"
        "    if (success) {\n"
        "      dat_cache_manager_->WriteDATFile(\n"
        "          false, std::move(*bundled_additional_dat_pending_write_));\n"
        "      loaded_bundled_additional_dat = true;\n"
        "    }\n"
        "    bundled_additional_dat_pending_write_.reset();\n"
        "  }\n\n"
        "  // The packaged DAT protects the first navigation immediately. Release\n"
        "  // Brave's one-time startup notification suppression so subscription\n"
        "  // providers can progressively replace the snapshot without a page reload.\n"
        "  if (loaded_bundled_additional_dat) {\n"
        "    filters_provider_manager_->ForceNotifyObservers(/*is_default_engine=*/false);\n"
        "  }\n\n"
        "  // If neither the profile cache nor the bundled baseline loaded, fall\n"
        "  // back to the existing live subscription aggregation path.\n"
        "  if (!success) {\n"
        "    if (is_default_engine) {\n"
        "      filters_provider_manager_->ForceNotifyObserver(*default_service_observer_,\n"
        "                                                     true);\n"
        "    } else if (bundled_additional_dat_attempted_) {\n"
        "      // The bundled asset was absent or invalid. Bypass startup suppression\n"
        "      // so live subscription providers can build the additional engine.\n"
        "      filters_provider_manager_->ForceNotifyObservers(\n"
        "          /*is_default_engine=*/false);\n"
        "    } else {\n"
        "      filters_provider_manager_->ForceNotifyObserver(\n"
        "          *additional_filters_service_observer_, false);\n"
        "    }\n"
        "  }\n"
        "  observers_.Notify(&Observer::OnDATLoaded, is_default_engine, success);\n"
        "}\n\n"
        "void AdBlockService::OnReadBundledAdditionalDATFile(\n"
        "    std::optional<DATFileDataBuffer> dat) {\n"
        "  DCHECK_CALLED_ON_VALID_SEQUENCE(sequence_checker_);\n"
        "  if (!dat || dat->empty()) {\n"
        "    OnDATLoaded(/*is_default_engine=*/false, /*success=*/false);\n"
        "    return;\n"
        "  }\n"
        "  bundled_additional_dat_pending_write_ = *dat;\n"
        "  additional_filters_service_observer_->OnDATFileRead(std::move(*dat));\n"
        "}\n"
    )
    return replace_once(source, old, new,
                        "void AdBlockService::OnReadBundledAdditionalDATFile(",
                        "service-bundled-dat-fallback")


def transform_brave_build_gn(source: str) -> str:
    old = (
        '  android_assets("brave_pak_assets") {\n'
        '    sources = [ "$root_out_dir/brave_resources.pak" ]\n\n'
        '    deps = [\n'
        '      "//brave:brave_file_assets",\n'
        '      "//brave:packed_resources_extra",\n'
        '    ]\n'
        '    disable_compression = true\n'
        '  }\n'
    )
    new = (
        '  # The bundled native DAT is memory-mapped directly from the APK.\n'
        '  # Keep it uncompressed and preserve its stable asset path.\n'
        '  android_assets("sandium_adblock_assets") {\n'
        '    renaming_sources = [\n'
        '      "$root_out_dir/gen/sandium_adblock/engine1.dat",\n'
        '      "$root_out_dir/gen/sandium_adblock/sources.json",\n'
        '    ]\n'
        '    renaming_destinations = [\n'
        '      "sandium/adblock/engine1.dat",\n'
        '      "sandium/adblock/sources.json",\n'
        '    ]\n'
        '    disable_compression = true\n'
        '  }\n\n'
        '  android_assets("brave_pak_assets") {\n'
        '    sources = [ "$root_out_dir/brave_resources.pak" ]\n\n'
        '    deps = [\n'
        '      "//brave:brave_file_assets",\n'
        '      "//brave:packed_resources_extra",\n'
        '      "//brave:sandium_adblock_assets",\n'
        '    ]\n'
        '    disable_compression = true\n'
        '  }\n'
    )
    return replace_once(source, old, new,
                        'android_assets("sandium_adblock_assets")',
                        "brave-uncompressed-dat-assets")


def verify(core: Path) -> None:
    cache_cc = read(core / "components/brave_shields/core/browser/ad_block_dat_cache_manager.cc")
    service_cc = read(core / "components/brave_shields/content/browser/ad_block_service.cc")
    build_gn = read(core / "BUILD.gn")
    checks = {
        "asset-path": ASSET_PATH in cache_cc,
        "android-asset-open": "OpenApkAsset" in cache_cc,
        "uncompressed-assets": '"sandium/adblock/engine1.dat"' in build_gn and "disable_compression = true" in build_gn,
        "only-on-cache-failure": "!success && !is_default_engine &&" in service_cc,
        "success-before-cache-write": "if (success) {\n      dat_cache_manager_->WriteDATFile(" in service_cc,
        "provider-refresh-after-bundled-dat": "filters_provider_manager_->ForceNotifyObservers(/*is_default_engine=*/false);" in service_cc,
        "normal-provider-fallback": "ForceNotifyObserver(\n          *additional_filters_service_observer_, false);" in service_cc,
        "force-live-provider-fallback-after-bundle-failure": "ForceNotifyObservers(\n          /*is_default_engine=*/false);" in service_cc,
        "no-homepage-warmup": "MaybeTriggerSandiumHomepageWarmup" not in service_cc and "recordNtpShown" not in service_cc,
    }
    failed = [name for name, okay in checks.items() if not okay]
    if failed:
        raise RuntimeError("SANDIUM_ADBLOCK_DAT_VERIFY=FAIL " + ",".join(failed))
    print("SANDIUM_ADBLOCK_DAT_VERIFY=PASS " + " ".join(f"{k}=true" for k in checks))


def apply(core: Path) -> None:
    files = (
        ("components/brave_shields/core/browser/ad_block_dat_cache_manager.h", transform_cache_header, "cache-manager-header"),
        ("components/brave_shields/core/browser/ad_block_dat_cache_manager.cc", transform_cache_cc, "cache-manager-implementation"),
        ("components/brave_shields/content/browser/ad_block_service.h", transform_service_header, "service-header"),
        ("components/brave_shields/content/browser/ad_block_service.cc", transform_service_cc, "service-implementation"),
        ("BUILD.gn", transform_brave_build_gn, "brave-asset-target"),
    )
    for relative, transform, label in files:
        path = core / relative
        before = read(path)
        after = transform(before)
        write(path, before, after, label)


def verify_pin(core: Path) -> None:
    tag = subprocess.run(["git", "-C", str(core), "describe", "--tags", "--exact-match"],
                         check=True, capture_output=True, text=True).stdout.strip()
    sha = subprocess.run(["git", "-C", str(core), "rev-parse", "HEAD"],
                         check=True, capture_output=True, text=True).stdout.strip()
    if tag != EXPECTED_CORE_TAG or sha != EXPECTED_CORE_SHA:
        raise SystemExit(f"SANDIUM_ADBLOCK_DAT_PIN=FAIL expected={EXPECTED_CORE_TAG}@{EXPECTED_CORE_SHA} actual={tag}@{sha}")
    print(f"SANDIUM_ADBLOCK_DAT_PIN=PASS {tag}@{sha}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", required=True, type=Path)
    args = parser.parse_args()
    core = args.core.resolve()
    if not core.is_dir():
        raise SystemExit(f"missing pinned Brave core: {core}")
    verify_pin(core)
    apply(core)
    verify(core)


if __name__ == "__main__":
    main()
