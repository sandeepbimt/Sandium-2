// SPDX-License-Identifier: MPL-2.0
#include "policy.h"
#include "style.h"
#include "subscription_policy.h"
#include <cassert>
#include <iostream>
using namespace sandium::port1442;
struct R {bool matched,has_exception,important;};
void ok(const char* name,bool b){if(!b){std::cerr<<"FAIL "<<name<<'\n';std::exit(1);}std::cout<<"PASS "<<name<<'\n';}
int main(int argc,char**){
  const auto css=HideStyles({".ad-slot", ".allow", "[data-creative]", ".video{display:none}@import 'x'", "@import 'https://remote.test/x'"}, {".allow"});
  if(argc>1){std::cout<<css;return 0;}
  ok("popup-exception",!PopupMatch(R{true,false,false},[](bool m,bool e){assert(m&&e);return R{false,true,false};}));
  ok("popup-secondary-match",PopupMatch(R{},[](bool m,bool e){assert(!m&&e);return R{true,false,false};}));
  ok("popup-primary-exception",!PopupMatch(R{false,true,false},[](bool m,bool e){assert(m&&!e);return R{true,false,false};}));
  ok("popup-no-match",!PopupMatch(R{},[](bool,bool){return R{};}));
  ok("important-extra",PopupMatch(R{false,true,false},[](bool,bool){return R{false,false,true};}));
  ok("important-primary-short-circuit",PopupMatch(R{false,false,true},[](bool,bool){std::abort();return R{};}));
  ok("slot-hide",css.find(".ad-slot { display:none !important; }")!=css.npos);
  ok("cosmetic-exception",css.find(".allow")==css.npos);
  ok("no-rule-declaration-injection",css.find("video")==css.npos && css.find("@import")==css.npos);
  std::set<std::string> generic_hide = {".scoped-ad"};
  int generic_queries = 0;
  auto generic = [&](const auto& classes, const auto& ids, const auto& except) {
    ++generic_queries;
    ok("generic-keys-bounded", classes.size()==6 && ids.size()==4);
    ok("generic-exceptions-pass-to-engine", except==std::vector<std::string>{"#ad-728x90"});
    return std::vector<std::string>{
      ".ad-160x600", "#Adsense300x250", "#ad-728x90",
      ".ad-160x600 .something-else", ".not-vetted", ".ad-160x600{color:red}",
    };
  };
  AppendPackagedGenericHide(false, {"#ad-728x90"}, generic_hide, generic);
  ok("generic-only-safe-exact-matches", generic_hide==std::set<std::string>{
      "#Adsense300x250", ".ad-160x600", ".scoped-ad"});
  generic_hide = {".scoped-ad"};
  AppendPackagedGenericHide(true, {"#ad-728x90"}, generic_hide, generic);
  ok("generichide-preserves-scoped-and-skips-query",
     generic_queries==1 && generic_hide==std::set<std::string>{".scoped-ad"});
  Subscription s;ok("fresh-profile-fetch",s.Due(100,true,false));s.attempt=s.success=100;
  ok("honor-expiry",!s.Due(101,false,false));ok("expired",s.Due(100+168*3600,false,false));
  s.attempt++;ok("retry-failure",s.Due(102,false,false));s.attempt=s.success;
  ok("manual-refresh",s.Due(101,false,true));s.enabled=false;ok("disabled-not-fetched",!s.Due(400000,true,true));
  s.enabled=true;s.deleted=true;ok("never-restore-deleted",!s.Due(400000,true,true));
}
