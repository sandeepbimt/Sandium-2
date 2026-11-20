// SPDX-License-Identifier: MPL-2.0
// Must link the actual patched Rust/CXX library; no adapter doubles here.
#include <cstdint>
#include <iostream>
#include <cstdlib>
#include <string_view>
#include <string>
#include <utility>
#include <vector>
#include "base/json/json_reader.h"
#include "components/sandium_adblock/network_decision.h"
#include "components/sandium_adblock/policy.h"
namespace {
auto Build(const std::string& text) {
  auto set=adblock::new_filter_set(false);
  const std::vector<uint8_t> bytes(text.begin(),text.end());
  auto parsed=set->add_filter_list_with_permissions(bytes,0);
  if (parsed.result_kind!=adblock::ResultKind::Success) std::abort();
  return adblock::engine_from_filter_set(std::move(set));
}
}
int main() {
  if (!adblock::set_domain_resolver()) return 1;
  auto a=Build("||blocked.test^$script\n||popup.test^$popup\n||onlynetwork.test^\n");
  auto b=Build("@@||blocked.test/allowed.js$script\n@@||popup.test/login$popup\n"
               "||ohjpfawpaap.in^$third-party,script,subdocument,image\n"
               "publisher.test##.empty-ad-slot\npublisher.test##.kept-slot\npublisher.test#@#.kept-slot\n");
  if(a.result_kind!=adblock::ResultKind::Success||b.result_kind!=adblock::ResultKind::Success)return 2;
  using R=blink::mojom::ResourceType;
  auto origin=url::Origin::Create(GURL("https://publisher.test/"));
  struct C{const char*url;R r;bool block;};
  const C cases[]={{"https://blocked.test/ad.js",R::kScript,true},{"https://blocked.test/allowed.js",R::kScript,false},
    {"https://safe.test/ad.js",R::kScript,false},{"https://ohjpfawpaap.in/a",R::kImage,true},
    {"https://ohjpfawpaap.in/a",R::kSubFrame,true},{"https://ohjpfawpaap.in/a",R::kMedia,false}};
  for(auto c:cases){auto m=sandium::adblock_native::MatchStandard(*a.value,*b.value,GURL(c.url),c.r,origin,"GET");
    if(sandium::adblock_native::ResolveDecision(m,{},"GET",false).history.blocked()!=c.block){std::cerr << "network mismatch: " << c.url << '\n';return 3;}}
  for(auto c : {std::pair{"https://popup.test/auction",true},std::pair{"https://popup.test/login",false},std::pair{"https://onlynetwork.test/",false},std::pair{"https://pay.test/return",false}}){
    GURL target(c.first);auto pass=[&](const adblock::Engine& e,bool prior,bool except){return e.matches(target.spec(),std::string(target.host()),std::string("publisher.test"),std::string("popup"),true,std::string("GET"),prior,except);};
    bool blocked=sandium::port1442::PopupMatch(pass(*a.value,false,true),[&](bool m,bool e){return pass(*b.value,m,e);});
    if(blocked!=c.second){std::cerr << "popup mismatch: " << c.first << '\n';return 4;}}
  auto raw=b.value->url_cosmetic_resources(std::string("https://publisher.test/"));
  auto info=base::JSONReader::ReadDict(std::string_view(raw.data(),raw.size()),base::JSON_PARSE_RFC);
  if(!info || !info->FindList("hide_selectors"))return 5;
  bool hide=false;for(const auto& value:*info->FindList("hide_selectors")){if(!value.is_string())continue;if(value.GetString()==".kept-slot")return 6;hide|=value.GetString()==".empty-ad-slot";}
  if (!hide) return 7;
  auto generic = Build("##.ad-160x600\n###ad-728x90\n"
                       "publisher.test#@#.ad-160x600\n"
                       "@@||no-generic.test^$generichide\n");
  if (generic.result_kind != adblock::ResultKind::Success) return 8;
  auto plain = generic.value->hidden_class_id_selectors(
      std::vector<std::string>{"ad-160x600"},
      std::vector<std::string>{"ad-728x90"}, std::vector<std::string>{});
  if (plain.result_kind != adblock::ResultKind::Success ||
      plain.value.size() != 2) return 9;
  auto excepted = generic.value->hidden_class_id_selectors(
      std::vector<std::string>{"ad-160x600"},
      std::vector<std::string>{"ad-728x90"}, std::vector<std::string>{".ad-160x600"});
  if (excepted.result_kind != adblock::ResultKind::Success ||
      excepted.value.size() != 1 ||
      std::string(excepted.value[0]) != "#ad-728x90") return 10;
  auto suppress_raw =
      generic.value->url_cosmetic_resources(std::string("https://no-generic.test/"));
  auto suppress = base::JSONReader::ReadDict(
      std::string_view(suppress_raw.data(), suppress_raw.size()), base::JSON_PARSE_RFC);
  if (!suppress || !suppress->FindBool("generichide").value_or(false)) return 11;
  std::cout << "RAWS_ENGINE_SMOKE_1442_PASS\n";
  return 0;
}
