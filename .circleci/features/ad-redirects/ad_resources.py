"""Include the recorded third-party ad network in Sandium's additional filter engine."""
import argparse
from pathlib import Path

PROVIDER = Path("components/brave_shields/content/browser/ad_block_custom_filters_provider.cc")
CACHE = Path("components/brave_shields/core/browser/ad_block_dat_cache_manager.cc")
CACHE_TESTS = (
    Path("components/brave_shields/content/test/ad_block_service_unittest.cc"),
    Path("browser/brave_shields/ad_block_dat_cache_browsertest.cc"),
)
RULE = "||ohjpfawpaap.in^$third-party,script,subdocument,image"
ADD_USER_FILTERS = "  (*filter_set)->add_filter_list_with_permissions(buffer, permission_mask);"
ADD_RESOURCES = rf'''  // EasyList 103ec37fca84a70da9e8dc517bcd65b5697a7fbd. Cover the third-party
  // player ad requests even while subscription mirrors catch up.
  constexpr std::string_view kSandiumAdResources =
      "! Title: Sandium player ad resources\n"
      "{RULE}\n";
  (*filter_set)->add_filter_list_with_permissions(
      DATFileDataBuffer(kSandiumAdResources.begin(), kSandiumAdResources.end()),
      /*permission_mask=*/0);
'''
CACHE_NAME = "engine1-sandium-ad-resources-v1.dat"
WRITE_DAT = """            base::ImportantFileWriter::WriteFileAtomically(
                cache_path, base::as_string_view(dat));"""
WRITE_AND_RETIRE_LEGACY = """            if (base::ImportantFileWriter::WriteFileAtomically(
                    cache_path, base::as_string_view(dat)) &&
                cache_path.BaseName() ==
                    base::FilePath::FromASCII(kAdBlockEngine1DATCache)) {
              base::DeleteFile(cache_path.DirName().AppendASCII("engine1.dat"));
            }"""


def replace(source, before, after, marker, count=1):
    if (source.count(after) == count and source.count(marker) == count
            and before not in source.replace(after, "")):
        return source
    if marker in source or source.count(before) != count:
        raise ValueError("Unexpected Brave source near " + marker)
    return source.replace(before, after)


def plan(core):
    changes = {}
    for relative in (PROVIDER, CACHE, *CACHE_TESTS):
        path = core / relative
        source = path.read_text()
        if relative == PROVIDER:
            result = replace(source, "#include <string>\n", "#include <string>\n#include <string_view>\n",
                             "#include <string_view>")
            result = replace(result, ADD_USER_FILTERS, ADD_RESOURCES + ADD_USER_FILTERS,
                             "constexpr std::string_view kSandiumAdResources")
        elif relative == CACHE:
            # Old additional DATs can bypass all filter providers on a warm start.
            # The existing missing-DAT path rebuilds once, from the installed lists.
            key = "constexpr char kAdBlockEngine1DATCache[] = "
            result = replace(source, key + '"engine1.dat";', key + '"' + CACHE_NAME + '";',
                             CACHE_NAME)
            result = replace(result, WRITE_DAT, WRITE_AND_RETIRE_LEGACY,
                             'base::DeleteFile(cache_path.DirName().AppendASCII("engine1.dat"))')
        else:
            marker = '"' + CACHE_NAME + '"'
            result = replace(source, '"engine1.dat"', marker, marker, 3)
        if result != source:
            changes[path] = result
    return changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("core", type=Path)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    changes = plan(args.core)
    if changes and args.verify_only:
        parser.error("Sandium player ad resource filter is missing")
    for path, source in changes.items():
        path.write_text(source)


if __name__ == "__main__":
    main()
