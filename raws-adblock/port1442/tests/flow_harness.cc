// Executes the source-ported #1442 navigation throttle. Clock, content settings,
// URL classes, Rust service replies and navigation lifecycle are test doubles.
#include <cassert>
#include <functional>
#include <iostream>
#include <map>
#include <memory>
#include <string>
#include <utility>
#define BUILDFLAG(x) 1
#define FROM_HERE 0
struct GURL {std::string s;bool SchemeIsHTTPOrHTTPS()const{return s.starts_with("https://")||s.starts_with("http://");}bool IsAboutBlank()const{return s=="about:blank";}};
namespace base {
struct SupportsUserData{struct Data{virtual ~Data()=default;};};
struct TimeDelta{int n=0;constexpr TimeDelta& operator-=(TimeDelta o){n-=o.n;return *this;}auto operator<=>(const TimeDelta&)const=default;};
constexpr TimeDelta Milliseconds(int n){return {n};}constexpr TimeDelta Seconds(int n){return {1000*n};}
int tick;struct TimeTicks{int n{};static TimeTicks Now(){return {tick};}TimeDelta operator-(TimeTicks o)const{return {n-o.n};}};
template<class T> struct W{T*p;std::weak_ptr<int> life;};template<class T>struct WeakPtrFactory{T*p;std::shared_ptr<int> token=std::make_shared<int>();explicit WeakPtrFactory(T*x):p(x){} W<T> GetWeakPtr(){return {p,token};}void InvalidateWeakPtrs(){token=std::make_shared<int>();}};
template<class T,class...B> auto BindOnce(void(T::*m)(bool),W<T>w,B...bound){return [=](auto...x){if(!w.life.expired())(w.p->*m)(bound...,x...);};}
struct OneShotTimer{static inline std::function<void()> fire;static inline int delay;template<class F>void Start(int,TimeDelta d,F fn){delay=d.n;fire=fn;}void Stop(){fire={};}};
}
enum class ContentSettingsType{POPUPS};constexpr int CONTENT_SETTING_ALLOW=1;struct Profile{static Profile* FromBrowserContext(void*){static Profile p;return &p;}};
struct Settings{int allowed=0;int GetContentSetting(const GURL&,const GURL&,ContentSettingsType){return allowed;}}settings;
struct HostContentSettingsMapFactory{static Settings* GetForProfile(Profile*){return &settings;}};
namespace content {
struct WebContents {std::map<const char*,std::unique_ptr<base::SupportsUserData::Data>>m;void*GetBrowserContext(){return nullptr;}auto*GetUserData(const char*k){auto i=m.find(k);return i==m.end()?nullptr:i->second.get();}template<class T>void SetUserData(const char*k,std::unique_ptr<T>x){m[k]=std::move(x);}void RemoveUserData(const char*k){m.erase(k);}};
struct RenderFrameHost{GURL url;RenderFrameHost* outer;GURL GetLastCommittedURL(){return url;}struct Origin{GURL GetURL(){return {"https://frame.test"};}};Origin GetLastCommittedOrigin(){return {};}RenderFrameHost* GetOutermostMainFrame(){return outer;}};
struct NavigationHandle{WebContents*contents;GURL url;bool primary=true,renderer=true,same=false;bool IsInPrimaryMainFrame(){return primary;}bool IsRendererInitiated(){return renderer;}bool IsSameDocument(){return same;}const GURL&GetURL(){return url;}WebContents*GetWebContents(){return contents;}};
struct NavigationThrottle;struct NavigationThrottleRegistry{NavigationHandle h;std::unique_ptr<NavigationThrottle>th;NavigationHandle&GetNavigationHandle(){return h;}void AddThrottle(std::unique_ptr<NavigationThrottle>t){th=std::move(t);}};
struct NavigationThrottle{enum ThrottleCheckResult{PROCEED,DEFER,CANCEL_AND_IGNORE};NavigationThrottleRegistry&r;int resumed=0,cancelled=0;explicit NavigationThrottle(NavigationThrottleRegistry&v):r(v){}virtual ~NavigationThrottle()=default;NavigationHandle*navigation_handle(){return &r.h;}virtual ThrottleCheckResult WillStartRequest()=0;virtual ThrottleCheckResult WillRedirectRequest()=0;virtual const char*GetNameForLogging()=0;void CancelDeferredNavigation(ThrottleCheckResult t){assert(t==CANCEL_AND_IGNORE);++cancelled;}void Resume(){++resumed;}};
}
struct ChromeContentBrowserClient{void OnSandiumScriptedPopupCreated(content::RenderFrameHost*,content::WebContents*);};
namespace sandium::adblock_native {std::function<void(bool)> reply;GURL last_target,last_source;bool g_offline_ready=true;
bool OfflineRulesReady(){return g_offline_ready;}
template<class F>void QueryPopup(GURL t,GURL s,F cb){last_target=t;last_source=s;reply=cb;}}
#include "adapted_nav.inc"
int main(){using T=content::NavigationThrottle;using Th=SandiumPopupNavigationThrottle;using namespace sandium::adblock_native;
  content::WebContents tab;content::RenderFrameHost outer{{"https://publisher.test"},nullptr},opener{{"about:blank"},&outer};
  content::NavigationThrottleRegistry r{{&tab,{"https://auth.test/login"}},nullptr};ChromeContentBrowserClient chrome;
  auto mark=[&]{chrome.OnSandiumScriptedPopupCreated(&opener,&tab);};auto add=[&]{Th::MaybeCreateAndAdd(r);};auto step=[&](const char*n,bool ok){if(!ok){std::cerr<<"FAIL "<<n<<'\n';std::exit(1);}std::cout<<"PASS flow "<<n<<'\n';};
  add();step("unmarked-new-tab-not-intercepted",!r.th);
  g_offline_ready=false;mark();add();
  step("first-cold-popup-retires-marker-without-waiting",
       r.th&&tab.m.empty()&&r.th->WillStartRequest()==T::PROCEED&&!reply&&!base::OneShotTimer::fire);
  r.th.reset();g_offline_ready=true;add();step("no-cold-popup-marker-reused",!r.th);
  mark();r.h.url.s="about:blank";add();step("blank-first-document-retains-provenance",!r.th&&tab.m.size()==1);
  r.h.url.s="https://auth.test/login";add();step("first-real-popup-once",r.th&&tab.m.empty());
  step("marked-login-checked",r.th->WillStartRequest()==T::DEFER&&last_source.s=="https://frame.test");base::tick+=35;reply(false);step("unmatched-login-resumes",r.th->resumed==1);
  base::tick+=500;r.h.url.s="https://pay.test/return";step("payment-redirect-only-remaining-budget",r.th->WillRedirectRequest()==T::DEFER&&base::OneShotTimer::delay==65);base::tick+=10;reply(false);step("legitimate-payment-redirect-resumes",r.th->resumed==2);
  r.h.url.s="https://ad.test/auction";step("marked-popunder-redirect-checked",r.th->WillRedirectRequest()==T::DEFER);reply(true);step("positive-popup-rule-cancels",r.th->cancelled==1);
  r.th.reset();mark();add();settings.allowed=1;step("explicit-popup-permission-bypass",r.th->WillStartRequest()==T::PROCEED);settings.allowed=0;
  step("late-result-test-defers",r.th->WillStartRequest()==T::DEFER);auto late=reply;auto timeout=base::OneShotTimer::fire;base::tick+=100;timeout();late(true);step("timeout-fails-open-and-late-block-ignored",r.th->resumed==1&&!r.th->cancelled);step("spent-budget-no-further-hold",r.th->WillRedirectRequest()==T::PROCEED);
  r.th.reset();mark();base::tick+=10001;add();step("expired-provenance-is-retired",!r.th&&tab.m.empty());
  mark();r.h.renderer=false;add();step("typed-or-bookmarked-navigation-clears-marker",!r.th&&tab.m.empty());
}
