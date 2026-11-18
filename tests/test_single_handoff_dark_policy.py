"""Dormant authority transform and actual injected policy methods with explicit doubles."""
import gzip,json,hashlib,importlib.util,pathlib,subprocess,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('dark_policy',ROOT/'experiments/single-handoff/dark_policy.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class DarkAuthority(unittest.TestCase):
 def test_pinned_transform_replay(self):
  out={};base=ROOT/'.circleci/features/dark-pages/renderer/fixtures'
  for p in m.BASE:
   text=out.get(p['path']) or (base/p['path']).read_text()
   self.assertEqual(text.count(p['old']),p.get('count',1))
   out[p['path']]=text.replace(p['old'],p['new'])
  for path in m.patches():
   text=m.transform(path,out[path]);self.assertEqual(text,m.transform(path,text))
   with self.assertRaises(ValueError):m.transform(path,'unknown source')
 def test_exact_gn_registration(self):
  fixture=json.loads(gzip.decompress((ROOT/'experiments/single-handoff/fixtures/content-registration.json.gz').read_bytes()))
  for p in m.REGISTRATION:
   item=fixture['files'][p];text=item['text'];self.assertEqual(hashlib.sha256(text.encode()).hexdigest(),item['sha256'])
   result=m.registration_transform(p,text);self.assertEqual(result,m.registration_transform(p,result))
   with self.assertRaises(ValueError):m.registration_transform(p,result+m.REGISTRATION[p][1])
 def test_typography_neighbors_and_constructor_order_preserved(self):
  dark_old=m.old_block(m.SETTINGS,'void SetSandiumDarkPageFlagsForCommit')
  original=(ROOT/'.circleci/features/dark-pages/renderer/fixtures'/m.SETTINGS).read_text()
  original=original.replace('  void SetFromStrings(const String& name, const String& value);',dark_old)
  typography='  void SetSandiumPageTextPolicyForCommit(int packed) { sandium_page_text_policy_ = packed; }\n'
  original=original.replace('  void SetFromStrings',typography+'  void SetFromStrings')
  transformed=m.transform(m.SETTINGS,original);self.assertIn(typography,transformed)
  source=(ROOT/'.circleci/features/dark-pages/renderer/fixtures'/m.NAV).read_text()
  for patch in m.BASE:
   if patch['path']==m.NAV:source=source.replace(patch['old'],patch['new'])
  page_text='  commit_params->sandium_page_text_policy = 100;\n'
  source=source.replace('  commit_params->sandium_dark_page_flags = -1;',page_text+'  commit_params->sandium_dark_page_flags = -1;')
  source=source.replace('/*sandium_dark_page_flags=*/-1, url::Origin(),','/*sandium_dark_page_flags=*/-1, /*sandium_page_text_policy=*/100, url::Origin(),')
  transformed=m.transform(m.NAV,source);self.assertIn(page_text,transformed)
  self.assertEqual(transformed.count('/*sandium_dark_page_flags=*/-1, /*sandium_dark_policy_revision=*/0, /*sandium_page_text_policy=*/100, url::Origin(),'),2)
 def runtime(self,mutate=False,revision_mutation=False):
  methods=m.SETTINGS_METHODS.split('  void SetFromStrings')[0]
  if revision_mutation:methods=methods.replace('revision == 0 || revision <= sandium_dark_policy_revision_','revision == 0')
  block=m.PREF_BLOCK
  if mutate:block=block.replace('sandium_frame->GetDocument()->Token().value() == *prefs.sandium_dark_document_token','true')
  code='''#include <cassert>
#include <cstdint>
#include <optional>
struct Settings {int sandium_dark_page_flags_=-1;uint64_t sandium_dark_policy_revision_=0;int changes=0;
void SetForceDarkModeEnabled(bool){} void SetSandiumDarkPageFlags(int x){sandium_dark_page_flags_=x;++changes;}
'''+methods+'''};
struct Token {int v;int value(){return v;}};struct Document {struct Token t{1};struct Token Token(){return t;}};
struct LocalFrame {Document doc;Document* GetDocument(){return &doc;}};
template<class T>T* DynamicTo(LocalFrame* f){return f;}
struct Page {Settings settings;LocalFrame frame;LocalFrame* MainFrame(){return &frame;}Settings& GetSettings(){return settings;}};
struct WebView {Page page;Page* GetPage(){return &page;}};
struct Prefs {bool force_dark_mode_enabled=false;int sandium_dark_page_flags=0;std::optional<int> sandium_dark_document_token;uint64_t sandium_dark_policy_revision=0;};
void apply(WebView* web_view_impl,Prefs prefs){auto* settings=&web_view_impl->page.settings;
'''+block+'''}
int main(){WebView w;auto& s=w.page.settings;s.SetSandiumDarkPageFlagsForCommit(1,10);
// New destination prefs must never recolor outgoing Document.
apply(&w,Prefs{false,0,2,30});assert(s.sandium_dark_page_flags_==1);
// Activation/commit installs target before any old queued preferences.
w.page.frame.doc.t.v=2;s.SetSandiumDarkPageFlagsForCommit(0,40);
apply(&w,Prefs{false,1,1,50});assert(s.sandium_dark_page_flags_==0);
apply(&w,Prefs{false,1,2,39});assert(s.sandium_dark_page_flags_==0);
// Live toggle still applies, equal or older revisions cannot undo it.
apply(&w,Prefs{false,1,2,41});assert(s.sandium_dark_page_flags_==1);
apply(&w,Prefs{false,0,2,41});assert(s.sandium_dark_page_flags_==1);
apply(&w,Prefs{false,-1,2,42});assert(s.sandium_dark_page_flags_==-1);
// Same URL reload still has a different document identity.
w.page.frame.doc.t.v=3;s.SetSandiumDarkPageFlagsForCommit(1,43);
apply(&w,Prefs{false,0,2,100});assert(s.sandium_dark_page_flags_==1);
apply(&w,Prefs{false,-2,3,101});assert(s.sandium_dark_page_flags_==1);
}'''
  with tempfile.TemporaryDirectory() as td:
   p=pathlib.Path(td);(p/'test.cc').write_text(code)
   subprocess.run(['g++','-std=c++20',str(p/'test.cc'),'-o',str(p/'test')],check=True,capture_output=True)
   return subprocess.run([str(p/'test')],capture_output=True).returncode
 def test_actual_injected_renderer_policy(self):self.assertEqual(self.runtime(),0)
 def test_missing_identity_guard_mutation_is_rejected(self):self.assertNotEqual(self.runtime(True),0)
 def test_missing_revision_guard_mutation_is_rejected(self):self.assertNotEqual(self.runtime(revision_mutation=True),0)
 def browser_runtime(self,remove_epoch_guard=False):
  block=m.CLIENT_BLOCK.split('void ChromeContentBrowserClient::OverrideWebPreferences(')[0]
  if remove_epoch_guard:block=block.replace('!content::IsCurrentSandiumDarkPolicyQuery(*weak_contents, query_revision) ||','')
  code='''#include <cassert>
#include <cstdint>
#include <optional>
#include <functional>
#define BUILDFLAG(x) 1
#define IS_ANDROID 1
template<class T>struct scoped_refptr{T* p;scoped_refptr(T* v):p(v){}T& operator*(){return *p;}};
struct GURL{bool SchemeIsHTTPOrHTTPS(){return true;}};
namespace content {struct SiteInstance{};uint64_t revision=0;uint64_t NextSandiumDarkPolicyRevision(){return ++revision;}bool IsCurrentSandiumDarkPolicyRevision(uint64_t r){return r==revision;} }
struct Frame {bool IsErrorDocument(){return false;}struct Origin{bool opaque(){return false;}};Origin GetLastCommittedOrigin(){return {};}GURL GetLastCommittedURL(){return {};}};
struct WebContents {bool alive=true;int token=1;uint64_t epoch=0;Frame frame;Frame* GetPrimaryMainFrame(){return &frame;}struct Weak{WebContents* p;operator bool(){return p->alive;}WebContents& operator*(){return *p;}};Weak GetWeakPtr(){return {this};}};
namespace content {uint64_t BeginSandiumDarkPolicyQuery(WebContents& w){return w.epoch=NextSandiumDarkPolicyRevision();}bool IsCurrentSandiumDarkPolicyQuery(WebContents& w,uint64_t r){return w.epoch==r;}std::optional<int> GetSandiumPrimaryDocumentToken(WebContents& w,const SiteInstance&){return w.token;}}
struct WebPreferences{int sandium_dark_page_flags=-2;std::optional<int> sandium_dark_document_token;uint64_t sandium_dark_policy_revision=0;};
namespace night_mode {struct WebContentsThemeClient {int flag=1;std::function<void()> callback;static WebContentsThemeClient* FromWebContents(WebContents*);int SandiumDarkPageFlags(GURL){int sample=flag;auto cb=std::move(callback);callback=nullptr;if(cb)cb();return sample;}};WebContentsThemeClient theme;WebContentsThemeClient* WebContentsThemeClient::FromWebContents(WebContents*){return &theme;}}
'''+block+'''
int main(){WebContents w;content::SiteInstance site;WebPreferences p;
night_mode::theme.callback=[&]{night_mode::theme.flag=0;assert(ApplySandiumCommittedDarkPolicy(&w,site,&p));};
assert(!ApplySandiumCommittedDarkPolicy(&w,site,&p));assert(p.sandium_dark_page_flags==0);assert(p.sandium_dark_policy_revision==2);
night_mode::theme.callback=[&]{w.token=2;};assert(!ApplySandiumCommittedDarkPolicy(&w,site,&p));assert(p.sandium_dark_document_token==1);
night_mode::theme.callback=[&]{w.alive=false;};assert(!ApplySandiumCommittedDarkPolicy(&w,site,&p));
w.alive=true;assert(ApplySandiumCommittedDarkPolicy(&w,site,&p));assert(p.sandium_dark_document_token==2);
WebContents other;WebPreferences other_p;night_mode::theme.flag=1;
night_mode::theme.callback=[&]{ApplySandiumCommittedDarkPolicy(&other,site,&other_p);};
assert(ApplySandiumCommittedDarkPolicy(&w,site,&p));assert(p.sandium_dark_page_flags==1);
}'''
  with tempfile.TemporaryDirectory() as td:
   p=pathlib.Path(td);(p/'test.cc').write_text(code)
   subprocess.run(['g++','-std=c++20',str(p/'test.cc'),'-o',str(p/'test')],check=True,capture_output=True)
   return subprocess.run([str(p/'test')],capture_output=True).returncode

 def test_actual_browser_query_reentry_and_document_change(self):self.assertEqual(self.browser_runtime(),0)
 def test_missing_browser_epoch_guard_mutation_rejected(self):self.assertNotEqual(self.browser_runtime(True),0)

 def test_actual_native_producer_prefixes_preserve_activation(self):
  def block(path,needle):return next(new for old,new in m.patches()[path] if needle in old)
  nav=m.old_block(m.NAV,'SanitizeRedirectsForCommit')
  for old,new in m.patches()[m.NAV]:
   if old in nav:nav=nav.replace(old,new)
  nav=nav.replace('  SanitizeRedirectsForCommit(common_params, commit_params);','')
  bf=block(m.BF,'auto* restored_main_frame').split('      for (const auto& rvh : render_view_hosts_to_restore) {')[0]
  pr=block(m.PR,'bool view_transition_state_consumed').split('  for (const auto& rvh : render_view_hosts) {')[0]
  code='''#include <cassert>
#include <cstdint>
#include <functional>
uint64_t sequence=0;uint64_t NextSandiumDarkPolicyRevision(){return ++sequence;}
struct Origin{bool opaque(){return false;}};struct URL{bool SchemeIsHTTPOrHTTPS(){return true;}};
template<class T>struct Weak{T* p;operator bool() const{return p&&p->alive;}T* operator->()const{return p;}T* get()const{return p;}};
struct Frame{bool alive=true;int token=1;bool IsOutermostMainFrame(){return true;}bool IsErrorDocument(){return false;}Origin GetLastCommittedOrigin(){return {};}URL GetLastCommittedURL(){return {};}Weak<Frame> GetWeakPtr(){return {this};}int GetDocumentToken(){return token;}};
struct WebContents{static WebContents* FromRenderFrameHost(Frame*){return nullptr;}};
struct Browser{std::function<void()> cb;int GetSandiumDarkPageFlagsForNavigation(WebContents*,URL){auto call=std::move(cb);cb=nullptr;if(call)call();return 1;}};
Browser browser_instance;struct Client{Browser* browser(){return &browser_instance;}} client;
Client* GetContentClient(){return &client;}
struct Params{int sandium_dark_page_flags=-1;uint64_t sandium_dark_policy_revision=0;bool is_view_source=false;};
struct Common{URL url;};
struct Owner{bool alive=true;int continued=0,last_flags=9;uint64_t last_revision=0;Frame frame;Frame replacement;Frame* current=&frame;
struct Factory{Owner* p;Weak<Owner> GetWeakPtr(){return {p};}} weak_factory_{this};
Weak<Owner> GetWeakPtr(){return {this};}Frame* current_frame_host(){return current;}
struct Ref{Owner* p;Frame* operator->(){return p->current;}Frame& get(){return *p->current;}} main_document_{this};
bool IsInOutermostMainFrame(){return true;}WebContents* GetWebContents(){return nullptr;}
void nav(){Common c;Common* common_params=&c;Params params;Params* commit_params=&params;Origin origin_to_commit;
'''+nav+'''
++continued;last_flags=params.sandium_dark_page_flags;last_revision=params.sandium_dark_policy_revision;}
void bf(){enum class RenderFrameHostLifecycleStateImpl{kInBackForwardCache};auto prev_state=RenderFrameHostLifecycleStateImpl::kInBackForwardCache;
'''+bf+'''
++continued;last_flags=sandium_policy;last_revision=sandium_revision;}}
void pr(){
'''+pr+'''
++continued;last_flags=sandium_policy;last_revision=sandium_revision;}
};
int main(){for(int route=0;route<3;++route){Owner o;auto run=[&]{if(route==0)o.nav();else if(route==1)o.bf();else o.pr();};run();assert(o.continued==1&&o.last_flags==1&&o.last_revision>0);
browser_instance.cb=[&]{o.alive=false;};run();assert(o.continued==1);
if(route>0){o.alive=true;browser_instance.cb=[&]{o.current=&o.replacement;};run();assert(o.continued==2&&o.last_flags==-2&&o.last_revision==0);}
}}
'''
  with tempfile.TemporaryDirectory() as td:
   p=pathlib.Path(td);(p/'test.cc').write_text(code)
   compiled=subprocess.run(['g++','-std=c++20',str(p/'test.cc'),'-o',str(p/'test')],capture_output=True,text=True)
   self.assertEqual(compiled.returncode,0,compiled.stderr)
   subprocess.run([str(p/'test')],check=True,capture_output=True)

 def test_actual_content_authority_helper(self):
  source=(ROOT/'experiments/single-handoff/components/content/browser/renderer_host/sandium_dark_policy_authority.cc').read_text()
  source='\n'.join(line for line in source.splitlines() if not line.startswith('#include'))
  code='''#include <cassert>
#include <cstdint>
#include <limits>
#include <optional>
#include <memory>
#include <map>
#define CHECK(x) assert(x)
namespace base {using UnguessableToken=int;struct SupportsUserData {struct Data {virtual ~Data()=default;};std::map<const void*,std::unique_ptr<Data>> data;Data* GetUserData(const void* k){auto i=data.find(k);return i==data.end()?nullptr:i->second.get();}void SetUserData(const void* k,std::unique_ptr<Data> d){data[k]=std::move(d);}};}
namespace content {struct BrowserThread{enum{UI};static bool CurrentlyOn(int){return true;}};struct SiteInstance{};
struct Frame {bool active=true,live=true;SiteInstance* site=nullptr;bool IsActive(){return active;}bool IsRenderFrameLive(){return live;}SiteInstance* GetSiteInstance(){return site;}};
struct RenderFrameHostImpl:Frame {int token=7;struct Token{int v;int value(){return v;}};Token GetDocumentToken(){return {token};}};
struct WebContents:base::SupportsUserData {RenderFrameHostImpl* frame=nullptr;Frame* GetPrimaryMainFrame(){return frame;}};}
'''+source+'''
int main(){using namespace content;SiteInstance site,other;RenderFrameHostImpl f;f.site=&site;WebContents a,b;a.frame=&f;
assert(GetSandiumPrimaryDocumentToken(a,site)==7);assert(!GetSandiumPrimaryDocumentToken(a,other));f.active=false;assert(!GetSandiumPrimaryDocumentToken(a,site));f.active=true;f.live=false;assert(!GetSandiumPrimaryDocumentToken(a,site));f.live=true;
auto ar=BeginSandiumDarkPolicyQuery(a);auto br=BeginSandiumDarkPolicyQuery(b);assert(br>ar);assert(IsCurrentSandiumDarkPolicyQuery(a,ar));assert(IsCurrentSandiumDarkPolicyQuery(b,br));auto newer=BeginSandiumDarkPolicyQuery(a);assert(!IsCurrentSandiumDarkPolicyQuery(a,ar));assert(IsCurrentSandiumDarkPolicyQuery(a,newer));assert(a.data.size()==1);assert(b.data.size()==1);
}
'''
  with tempfile.TemporaryDirectory() as td:
   p=pathlib.Path(td);(p/'test.cc').write_text(code)
   compiled=subprocess.run(['g++','-std=c++20',str(p/'test.cc'),'-o',str(p/'test')],capture_output=True,text=True)
   self.assertEqual(compiled.returncode,0,compiled.stderr)
   subprocess.run([str(p/'test')],check=True,capture_output=True)

if __name__=='__main__':unittest.main()
