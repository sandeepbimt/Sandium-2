"""Check the generated native resource rule and the additional-engine cache upgrade."""
from pathlib import Path
import subprocess
import tempfile
import unittest

import ad_resources as overlay


class AdResourcesTest(unittest.TestCase):
    def run_native(self, source):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "ad-resource-test"
            subprocess.run(["c++", "-std=c++17", "-x", "c++", "-", "-o", str(executable)],
                           input=source, text=True, check=True)
            subprocess.run([str(executable)], cwd=directory, check=True)

    def test_overlay_replay_and_source_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = {
                overlay.PROVIDER: "#include <string>\n" + overlay.ADD_USER_FILTERS,
                overlay.CACHE: 'constexpr char kAdBlockEngine1DATCache[] = "engine1.dat";\n'
                               + overlay.WRITE_DAT,
                **{path: 'cache_dir.AppendASCII("engine1.dat")\n' * 3
                   for path in overlay.CACHE_TESTS},
            }
            for name, source in inputs.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(source)
            changes = overlay.plan(root)
            self.assertEqual(set(changes), {root / name for name in inputs})
            for path, source in changes.items():
                path.write_text(source)
            self.assertEqual(overlay.plan(root), {})

            # A partial/duplicated cache filename edit cannot pass verification.
            broken = root / overlay.CACHE_TESTS[0]
            broken.write_text(broken.read_text() + '"engine1.dat"')
            with self.assertRaises(ValueError):
                overlay.plan(root)

    def test_native_provider_adds_separate_unprivileged_rules(self):
        native = r'''
#include <cassert>
#include <string>
#include <string_view>
#include <vector>
using DATFileDataBuffer = std::vector<unsigned char>;
struct Filters {
  std::vector<std::string> lists;
  std::vector<int> permissions;
  void add_filter_list_with_permissions(const DATFileDataBuffer& bytes, int mask) {
    lists.emplace_back(bytes.begin(), bytes.end());
    permissions.push_back(mask);
  }
};
int main() {
  Filters filters;
  auto* instance = &filters;
  auto** filter_set = &instance;
  int permission_mask = 255;
  std::string custom = "@@||ohjpfawpaap.in^$image";
  DATFileDataBuffer buffer(custom.begin(), custom.end());
  EMIT_FILTERS
  assert(filters.lists.size() == 2);
  assert(filters.lists[0] == "! Title: Sandium player ad resources\n"
         "||ohjpfawpaap.in^$third-party,script,subdocument,image\n");
  assert(filters.permissions[0] == 0);
  assert(filters.lists[1] == custom && filters.permissions[1] == 255);
}
'''
        native = native.replace("EMIT_FILTERS", overlay.ADD_RESOURCES + overlay.ADD_USER_FILTERS)
        self.run_native(native)

    def test_legacy_dat_retired_only_after_successful_additional_write(self):
        native = r'''
#include <cassert>
#include <filesystem>
#include <fstream>
#include <string>
namespace fs = std::filesystem;
namespace base {
struct FilePath {
  fs::path path;
  static FilePath FromASCII(const std::string& name) { return {name}; }
  FilePath BaseName() const { return {path.filename()}; }
  FilePath DirName() const { return {path.parent_path()}; }
  FilePath AppendASCII(const std::string& name) const { return {path / name}; }
  bool operator==(const FilePath& other) const { return path == other.path; }
};
void DeleteFile(FilePath file) { fs::remove(file.path); }
std::string as_string_view(const std::string& value) { return value; }
struct ImportantFileWriter {
  static bool WriteFileAtomically(FilePath file, const std::string& value) {
    if (value.empty()) return false;
    std::ofstream(file.path) << value;
    return true;
  }
};
}
constexpr char kAdBlockEngine1DATCache[] = "CACHE_NAME";
void Write(base::FilePath cache_path, const std::string& dat) {
  EMIT_WRITE
}
int main() {
  std::ofstream("engine1.dat") << "legacy";
  Write({"engine0.dat"}, "default");
  assert(fs::exists("engine1.dat"));
  Write({kAdBlockEngine1DATCache}, "");
  assert(fs::exists("engine1.dat") && !fs::exists(kAdBlockEngine1DATCache));
  Write({kAdBlockEngine1DATCache}, "replacement");
  assert(fs::exists(kAdBlockEngine1DATCache) && !fs::exists("engine1.dat"));
  assert(fs::exists("engine0.dat"));
}
'''
        self.run_native(native.replace("CACHE_NAME", overlay.CACHE_NAME)
                        .replace("EMIT_WRITE", overlay.WRITE_AND_RETIRE_LEGACY))


if __name__ == "__main__":
    unittest.main()
