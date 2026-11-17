#include "brave/components/sandium_ubo/materializer.h"
#include <set>
#include <string_view>
#include <utility>
#include "base/files/file_enumerator.h"
#include "base/files/file_util.h"
#include "base/files/scoped_temp_dir.h"
#include "base/json/json_reader.h"
#include "base/strings/string_number_conversions.h"
#include "base/strings/string_util.h"
#include "brave/components/sandium_ubo/disk_resources.h"
#include "crypto/sha2.h"
#include "extensions/common/extension_l10n_util.h"
#include "ui/base/resource/resource_bundle.h"

namespace sandium_ubo {
namespace {
bool Matches(std::string_view bytes, const std::string& expected) {
  return base::ToLowerASCII(base::HexEncode(crypto::SHA256HashString(bytes))) ==
         expected;
}
bool SafePath(const base::FilePath& root, const base::FilePath& relative) {
  if (relative.empty() || relative.IsAbsolute() || relative.ReferencesParent())
    return false;
  base::FilePath current = root.Append(relative);
  while (current != root) {
    if (base::IsLink(current)) return false;
    current = current.DirName();
  }
  return !base::IsLink(root);
}
bool ValidateDirectory(const base::FilePath& root,
                       const std::vector<Asset>& assets) {
  std::set<base::FilePath> allowed;
  for (const auto& asset : assets) {
    base::FilePath relative = base::FilePath::FromUTF8Unsafe(asset.path);
    if (!SafePath(root, relative)) return false;
    std::string bytes;
    if (!base::ReadFileToString(root.Append(relative), &bytes) ||
        !Matches(bytes, asset.digest)) return false;
    for (auto path = root.Append(relative); path != root; path = path.DirName())
      allowed.insert(path);
  }
  base::FileEnumerator entries(root, true, base::FileEnumerator::FILES |
      base::FileEnumerator::DIRECTORIES | base::FileEnumerator::SHOW_SYM_LINKS);
  for (auto path = entries.Next(); !path.empty(); path = entries.Next()) {
    if (base::IsLink(path) || !allowed.contains(path)) return false;
  }
  return true;
}
}  // namespace

std::vector<Asset> CaptureAssets() {
  std::vector<Asset> assets;
  for (const auto& resource : kSandiumUboDiskResources) {
    assets.push_back({resource.path, resource.sha256,
        ui::ResourceBundle::GetSharedInstance().LoadDataResourceString(resource.id)});
  }
  return assets;
}

std::optional<PreparedComponent> PrepareComponent(
    base::FilePath profile_path, std::vector<Asset> assets) {
  if (assets.empty() || !profile_path.IsAbsolute()) return std::nullopt;
  for (const auto& asset : assets) {
    if (!Matches(asset.bytes, asset.digest)) return std::nullopt;
  }
  const auto root = profile_path.AppendASCII("SandiumUboComponents");
  if (base::IsLink(root) || !base::CreateDirectory(root)) return std::nullopt;
  const auto directory = root.AppendASCII(kSandiumUboPayloadDigest);
  if (base::IsLink(directory)) return std::nullopt;
  if (!base::PathExists(directory)) {
    base::ScopedTempDir staging;
    if (!staging.CreateUniqueTempDirUnderPath(root)) return std::nullopt;
    for (const auto& asset : assets) {
      auto relative = base::FilePath::FromUTF8Unsafe(asset.path);
      if (!SafePath(staging.GetPath(), relative)) return std::nullopt;
      auto path = staging.GetPath().Append(relative);
      if (!base::CreateDirectory(path.DirName()) ||
          !base::WriteFile(path, asset.bytes)) return std::nullopt;
    }
    if (!ValidateDirectory(staging.GetPath(), assets)) return std::nullopt;
    // A single sequenced extension file runner owns installation. Never replace
    // any existing generation, and leave old generations/user settings intact.
    if (base::PathExists(directory) ||
        !base::Move(staging.GetPath(), directory)) return std::nullopt;
  }
  if (!ValidateDirectory(directory, assets)) return std::nullopt;
  std::string manifest_json;
  if (!base::ReadFileToString(directory.AppendASCII("manifest.json"),
                            &manifest_json)) return std::nullopt;
  auto manifest = base::JSONReader::ReadDict(
      manifest_json, base::JSON_PARSE_CHROMIUM_EXTENSIONS);
  std::string error;
  if (!manifest || !extension_l10n_util::LocalizeExtension(
      directory, &*manifest,
      extension_l10n_util::GzippedMessagesPermission::kDisallow, &error))
    return std::nullopt;
  return PreparedComponent{directory, std::move(*manifest)};
}
}  // namespace sandium_ubo
