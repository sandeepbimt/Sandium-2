// Chromium boundary doubles. SameDomainOrHost is stubbed to host equality;
// this suite does NOT validate Chromium's PSL, URL canonicalization or Mojo.
#include <string>
#include <string_view>
#include <vector>
#include <iostream>
#include <cstdlib>
#define BUILDFLAG(x) 1
struct GURL { std::string s; GURL()=default; GURL(const char*x):s(x){}; bool SchemeIsHTTPOrHTTPS() const{return s.starts_with("https://")||s.starts_with("http://");}
 std::string_view host()const {auto x=std::string_view(s);auto i=x.find("://");if(i==x.npos)return {};x.remove_prefix(i+3);return x.substr(0,x.find_first_of("/?"));}
 std::string_view path()const {auto x=std::string_view(s);auto i=x.find('/',x.find("://")+3);if(i==x.npos)return {};x.remove_prefix(i);return x.substr(0,x.find('?'));}
 std::string_view query()const{auto i=s.find('?');return i==s.npos?std::string_view{}:std::string_view(s).substr(i+1);}};
namespace net {namespace registry_controlled_domains {enum Mode{INCLUDE_PRIVATE_REGISTRIES};bool SameDomainOrHost(const GURL&a,const GURL&b,Mode){return a.host()==b.host();}}
struct QueryIterator{std::vector<std::pair<std::string_view,std::string_view>> kv;size_t i=0;QueryIterator(const GURL& u){auto q=u.query();while(!q.empty()){auto j=q.find('&');auto p=q.substr(0,j);auto e=p.find('=');kv.emplace_back(p.substr(0,e),e==p.npos?std::string_view{}:p.substr(e+1));if(j==q.npos)break;q.remove_prefix(j+1);}}bool IsAtEnd()const{return i==kv.size();} void Advance(){++i;}auto GetKey(){return kv.at(i).first;}auto GetValue(){return kv.at(i).second;}};}
enum class WindowOpenDisposition {kNewForegroundTab,kNewBackgroundTab,kNewWindow,kNewPopup,kCurrentTab};enum class ContentSettingsType{POPUPS};constexpr int CONTENT_SETTING_ALLOW=1;
namespace content {struct RenderFrameHost{bool child;struct Origin{GURL GetURL(){return GURL("https://frame.test/");}};Origin GetLastCommittedOrigin(){return {};}void* GetParent(){return child?this:nullptr;}void* GetBrowserContext(){return nullptr;}};}
struct Profile{static Profile* FromBrowserContext(void*){static Profile p;return &p;}}; struct Map{int permission=0;int GetContentSetting(GURL,GURL,ContentSettingsType){return permission;}};Map map;
struct HostContentSettingsMapFactory {static Map* GetForProfile(Profile*){return &map;}};
#include "adapted_early.inc"
int main(){ using D=WindowOpenDisposition;struct C{const char* name;const char* target;bool child;bool block;}; C cs[]={
{"auction","https://ad.test/?scontext_r=x&nrb=1&md=z&param_3=nortb_fallback",false,true},
{"normal-new-tab","https://news.test/article",false,false},{"login","https://auth.test/authorize?scontext_r=x&state=1",false,false},
{"payment-return","https://pay.test/callback?psid=842",true,false},{"server-switch","https://video.test/server/10?psid=842",true,false},
{"embedded-exchange","https://ad.test/10/0123456789abcdef0123456789ABCDEF?psid=13",true,true},
{"non-embedded","https://ad.test/10/0123456789abcdef0123456789ABCDEF?psid=13",false,false},
{"non-numeric-id","https://ad.test/10/0123456789abcdef0123456789ABCDEF?psid=1x",true,false},
{"same-frame-site","https://frame.test/10/0123456789abcdef0123456789ABCDEF?psid=1",true,false},
{"same-publisher","https://publisher.test/?scontext_r=x&nrb=1&md=v&param_3=nortb_fallback",true,false},
{"reordered-first-parameter","https://ad.test/?md=v&scontext_r=x&nrb=1&param_3=nortb_fallback",true,false},
{"last-nrb-wins","https://ad.test/?scontext_r=x&nrb=1&md=v&param_3=nortb_fallback&nrb=0",true,false}};
for(auto c:cs){content::RenderFrameHost f{c.child};auto check=[&](D d){return ShouldBlockSandiumAdTab(&f,"about:blank","https://publisher.test/",c.target,d);};map.permission=0;if(check(D::kNewPopup)!=c.block||check(D::kCurrentTab))return 1;map.permission=1;if(check(D::kNewPopup))return 2;std::cout<<"PASS early-guard "<<c.name<<" (with current-tab and explicit-allow controls)\n";}}
