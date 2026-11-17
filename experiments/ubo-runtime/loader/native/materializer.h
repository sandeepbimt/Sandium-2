#ifndef BRAVE_COMPONENTS_SANDIUM_UBO_MATERIALIZER_H_
#define BRAVE_COMPONENTS_SANDIUM_UBO_MATERIALIZER_H_
#include <optional>
#include <string>
#include <vector>
#include "base/files/file_path.h"
#include "base/values.h"
namespace sandium_ubo {
struct Asset {
  std::string path;
  std::string digest;
  std::string bytes;
};
struct PreparedComponent {
  base::FilePath directory;
  base::DictValue manifest;
};
// Snapshot immutable bundled resources before leaving the browser sequence.
std::vector<Asset> CaptureAssets();
// Blocking file/hash/localization work. Never accesses Profile or browser UI.
std::optional<PreparedComponent> PrepareComponent(
    base::FilePath profile_path, std::vector<Asset> assets);
}  // namespace sandium_ubo
#endif
