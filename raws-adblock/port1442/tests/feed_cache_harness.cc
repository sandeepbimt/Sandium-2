// SPDX-License-Identifier: MPL-2.0
// Tests actual emitted admission/cache code against fake persistence/parser.
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <memory>
#include <optional>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

constexpr size_t kListLimit=5u<<20;
constexpr size_t kMaxRulesBytes=8u<<20;
using DATFileDataBuffer=std::vector<uint8_t>;
std::string last_good="old valid data";
bool can_write=true;
namespace base {
bool IsStringUTF8(const std::string& s) {return s.find('\xff')==s.npos;}
struct Dir {const char* AppendASCII(const char* filename) {return filename;}};
bool CreateDirectory(Dir) {return can_write;}
struct ImportantFileWriter {
  static bool WriteFileAtomically(const char*, const std::string& raw) {
    last_good=raw;
    return true;
  }
};
}  // namespace base
namespace adblock {
enum class ResultKind {Success, Failure};
struct Meta {struct {bool has_value; uint16_t value;} expires_hours;};
Meta read_list_metadata(const DATFileDataBuffer& bytes) {
  std::string s(bytes.begin(),bytes.end());
  if(s.find("0-hours")!=s.npos) return {{true,0}};
  if(s.find("excess-expiry")!=s.npos) return {{true,800}};
  return {{false,0}};
}
struct Filters {
  struct AddResult {ResultKind result_kind=ResultKind::Success;};
  AddResult add_filter_list_with_permissions(
      const DATFileDataBuffer& bytes,uint8_t permissions) {
    assert(permissions==0);
    text.assign(bytes.begin(),bytes.end());return {};
  }
  std::string text;
};
auto new_filter_set(bool debug) {assert(!debug);return std::make_unique<Filters>();}
struct Engine {
  struct Source {size_t network_filter_count;size_t cosmetic_filter_count;};
  struct Report {std::vector<Source> source_info;};
  Report get_debug_info() {return {{counts}};}
  Source counts;
};
struct Result {ResultKind result_kind;std::unique_ptr<Engine> value;};
Result engine_from_filter_set(std::unique_ptr<Filters> f) {
  if(f->text.find("engine-error")!=f->text.npos)return {ResultKind::Failure,{}};
  return {ResultKind::Success,std::make_unique<Engine>(Engine{{
      size_t(f->text.find("||ads.test^")!=f->text.npos),
      size_t(f->text.find("example.test##.ad")!=f->text.npos)}})};
}
}  // namespace adblock
void PruneSandiumSubscription(DATFileDataBuffer& bytes) {
  std::string s(bytes.begin(),bytes.end());
  if (s.starts_with("!#if blocked")) bytes.clear();
}
namespace adblock_native {
#include "inspect_subscription_actual.inc"
}
struct Key {const char* key;};
Key kCatalog[]={{"stable-cache-key"}};
class ListCache {
 public:
#include "feed_store_actual.inc"
 private:
  base::Dir dir_;
};

int main() {
  ListCache cache;
  assert(cache.Store(0,"! just comments\n")==-1);
  assert(cache.Store(0,"!#if blocked\n||ads.test^")==-1);
  assert(cache.Store(0,"\xef\xbb\xbf \n<html>not a filter</html>")==-1);
  assert(cache.Store(0,"\xff invalid UTF-8")==-1);
  assert(cache.Store(0,"engine-error\n||ads.test^")==-1);
  assert(last_good=="old valid data");
  assert(cache.Store(0,"! excess-expiry\n||ads.test^")==168);
  assert(last_good=="! excess-expiry\n||ads.test^");
  assert(cache.Store(0,"! 0-hours\nexample.test##.ad")==0);
  assert(last_good=="! 0-hours\nexample.test##.ad");
  can_write=false;
  assert(cache.Store(0,"||ads.test^")==-1);
  assert(last_good=="! 0-hours\nexample.test##.ad");
}
