#!/usr/bin/env python3
"""Offline regression tests for Sandium's bundled DAT fallback patcher."""
from __future__ import annotations

import runpy
from pathlib import Path

PATCHER = runpy.run_path(str(Path(__file__).with_name("apply-sandium-adblock-dat-cache.py")))


def test_idempotent(name: str, source: str) -> None:
    transform = PATCHER[name]
    once = transform(source)
    twice = transform(once)
    assert once == twice, f"{name} is not idempotent"


def main() -> None:
    header = """  void MaybeReadCachedDATFiles(
      base::OnceCallback<void(std::optional<DATFileDataBuffer>,
                              std::optional<DATFileDataBuffer>)> on_complete);
"""
    test_idempotent("transform_cache_header", header)

    service_header = """  void OnReadCachedDATFiles(std::optional<DATFileDataBuffer> default_dat,
                            std::optional<DATFileDataBuffer> additional_dat);
  bool default_filter_list_loaded_for_testing_ = false;
  bool additional_filter_list_loaded_for_testing_ = false;

  SEQUENCE_CHECKER(sequence_checker_);
"""
    test_idempotent("transform_service_header", service_header)

    cache_cc = """#include "base/files/file_path.h"

std::pair<std::optional<DATFileDataBuffer>, std::optional<DATFileDataBuffer>>
ReadCachedDATFilesFromDisk(base::FilePath cache_dir) {
  base::FilePath default_engine_dat_file =
      cache_dir.AppendASCII(kAdBlockEngine0DATCache);
  base::FilePath additional_engine_dat_file =
      cache_dir.AppendASCII(kAdBlockEngine1DATCache);

  return std::make_pair(base::ReadFileToBytes(default_engine_dat_file),
                        base::ReadFileToBytes(additional_engine_dat_file));
}

}  // namespace

void AdBlockDATCacheManager::MaybeReadCachedDATFiles(
    base::OnceCallback<void(std::optional<DATFileDataBuffer>,
                            std::optional<DATFileDataBuffer>)> on_complete) {
  CHECK(base::FeatureList::IsEnabled(features::kAdblockDATCache));
  task_runner_->PostTaskAndReplyWithResult(
      FROM_HERE, base::BindOnce(&ReadCachedDATFilesFromDisk, cache_dir_),
      base::BindOnce(
          [](base::OnceCallback<void(std::optional<DATFileDataBuffer>,
                                     std::optional<DATFileDataBuffer>)>
                 callback,
             std::pair<std::optional<DATFileDataBuffer>,
                       std::optional<DATFileDataBuffer>> result) {
            std::move(callback).Run(std::move(result.first),
                                    std::move(result.second));
          },
          std::move(on_complete)));
}

}  // namespace brave_shields
"""
    transformed_cache = PATCHER["transform_cache_cc"](cache_cc)
    assert "OpenApkAsset(\"assets/sandium/adblock/engine1.dat\"" in transformed_cache
    assert "base::File asset_file(asset_fd);" in transformed_cache
    assert "!asset_file.IsValid() || region.size == 0" in transformed_cache
    assert "mapped_asset.Initialize(std::move(asset_file), region)" in transformed_cache
    assert "MaybeReadBundledAdditionalDATFile" in transformed_cache
    assert PATCHER["transform_cache_cc"](transformed_cache) == transformed_cache

    service = """void AdBlockService::OnDATLoaded(bool is_default_engine, bool success) {
  DCHECK_CALLED_ON_VALID_SEQUENCE(sequence_checker_);
  if (is_default_engine) {
    default_dat_loaded_for_testing_ = true;
  } else {
    additional_dat_loaded_for_testing_ = true;
  }
  // If the cached DAT failed to load, fall back to loading from filter lists.
  if (!success) {
    if (is_default_engine) {
      filters_provider_manager_->ForceNotifyObserver(*default_service_observer_,
                                                     true);
    } else {
      filters_provider_manager_->ForceNotifyObserver(
          *additional_filters_service_observer_, false);
    }
  }
  observers_.Notify(&Observer::OnDATLoaded, is_default_engine, success);
}
"""
    patched = PATCHER["transform_service_cc"](service)
    assert "!success && !is_default_engine" in patched
    assert "MaybeReadBundledAdditionalDATFile" in patched
    assert patched.index("if (success) {") < patched.index("WriteDATFile(")
    assert "ForceNotifyObservers(/*is_default_engine=*/false);" in patched
    assert patched.index("loaded_bundled_additional_dat = true;") < patched.index("ForceNotifyObservers(")
    assert "ForceNotifyObserver(\n          *additional_filters_service_observer_, false);" in patched
    assert "ForceNotifyObservers(\n          /*is_default_engine=*/false);" in patched
    assert "MaybeTriggerSandiumHomepageWarmup" not in patched

    build = """if (is_android) {
  android_assets("brave_file_assets") {
    sources = [ "//brave/LICENSE.html" ]
    disable_compression = false
  }

  android_assets("brave_pak_assets") {
    sources = [ "$root_out_dir/brave_resources.pak" ]

    deps = [
      "//brave:brave_file_assets",
      "//brave:packed_resources_extra",
    ]
    disable_compression = true
  }
}
"""
    transformed = PATCHER["transform_brave_build_gn"](build)
    assert '"sandium/adblock/engine1.dat"' in transformed
    assert "disable_compression = true" in transformed
    assert "//brave:sandium_adblock_assets" in transformed
    assert PATCHER["transform_brave_build_gn"](transformed) == transformed

    print("SANDIUM_ADBLOCK_DAT_PATCHER_TEST=PASS idempotent=true fallback=on_cache_miss_or_invalid "
          "write=after_native_deserialize assets=uncompressed warmup=absent")


if __name__ == "__main__":
    main()
