import importlib.util,pathlib,subprocess,tempfile,unittest,json,hashlib
P=pathlib.Path;HERE=P(__file__).parent
s=importlib.util.spec_from_file_location('ad',HERE/'apply.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)

class Tests(unittest.TestCase):
 def test_fixture_hashes(self):
  manifest=json.loads((HERE/'fixtures/manifest.json').read_text())
  for path,digest in manifest['sha256'].items():
   self.assertEqual(hashlib.sha256((HERE/'fixtures'/path).read_bytes()).hexdigest(),digest)

 def test_actual_pinned_callback_graph_replay(self):
  source=(HERE/'fixtures'/m.PATH).read_text()
  out=m.transform(source);self.assertEqual(out,m.transform(out))
  self.assertIn('next_callback, ctx, BeginSandiumAdDiagnostic(ctx)',out)
  self.assertIn('previous_result, diagnostic);',out)
  self.assertIn('ctx, diagnostic));',out)
  self.assertIn('diagnostic.cname_query = true;',out)
  self.assertIn('ReportSandiumAdDiagnostic(diagnostic, 3,',out)
  self.assertEqual(out.count('ReportSandiumAdDiagnostic(diagnostic, 5,'),2)
  for word in ('request_url','getURL','new_url_spec','mock_data_url','devtools_request_id'):
   self.assertNotIn(word,m.HELPERS)
 def test_fail_closed(self):
  with self.assertRaises(ValueError):m.transform('unexpected source')
 def test_compiled_production_helpers(self):
  with tempfile.TemporaryDirectory() as d:
   p=P(d)/'test.cc';p.write_text('''#include <cstdint>
#include <array>
#include <vector>
#include <memory>
#include <cassert>
namespace base{struct TimeDelta{int64_t value;int64_t InMicroseconds()const{return value;}};struct TimeTicks{int64_t t=0;static TimeTicks Now(){static int64_t n=0;return {++n};}TimeDelta since_origin()const{return {t};}friend TimeDelta operator-(TimeTicks a,TimeTicks b){return {a.t-b.t};}};}
namespace content{struct BrowserThread{enum ID{UI};static inline bool ui=true;static bool CurrentlyOn(ID){return ui;}};struct GlobalRenderFrameHostToken{int n=1;};struct WebContents;struct RenderFrameHost{static inline RenderFrameHost* current=nullptr;WebContents* wc=nullptr;static RenderFrameHost* FromFrameToken(GlobalRenderFrameHostToken){return current;}};struct WebContents{bool priv=false;static WebContents* FromRenderFrameHost(RenderFrameHost* f){return f?f->wc:nullptr;}};struct Browser{int64_t epoch=1;int omitted=0;std::vector<std::vector<double>> rows;int64_t GetSandiumNavigationDiagnosticsEpoch(WebContents* w){return w&&!w->priv?epoch:0;}void RecordSandiumNavigationDiagnosticForEpoch(WebContents* w,int64_t e,int code,int64_t,int64_t,const std::vector<double>& v){if(!w||w->priv||e!=epoch)return;if(code==24)omitted++;else if(code==11) rows.push_back(v);}};struct ContentClient{Browser browser_;Browser* browser(){return &browser_;}};ContentClient client;struct ContentBrowserClient{static int64_t SandiumDiagnosticsEpoch(WebContents* w){return client.browser_.GetSandiumNavigationDiagnosticsEpoch(w);}static void RecordSandiumDiagnosticForEpoch(WebContents* w,int64_t e,int c,int64_t n,int64_t t,const std::vector<double>& v){client.browser_.RecordSandiumNavigationDiagnosticForEpoch(w,e,c,n,t,v);}};}
struct Service{std::array<std::array<int64_t,6>,4> GetSandiumDiagnosticLoadSnapshot(){return {{{0,0,-1,0,-1,1},{0,1,-1,0,-1,1},{1,0,-1,0,-1,1},{1,1,-1,0,-1,1}}};}};struct Process{Service service;Service* ad_block_service(){return &service;}};Process process;Process* g_brave_browser_process=&process;
struct BraveRequestInfo{content::GlobalRenderFrameHostToken render_frame_token(){return {};}int resource_type(){return 7;}};
struct EngineFlags{bool did_match_rule=false,did_match_exception=false,did_match_important=false;};
'''+m.HELPERS+'''int main(){auto ctx=std::make_shared<BraveRequestInfo>();content::WebContents w;content::RenderFrameHost f;f.wc=&w;content::RenderFrameHost::current=&f;auto& b=content::client.browser_;
w.priv=true;assert(BeginSandiumAdDiagnostic(ctx).epoch==0);w.priv=false;
auto first=BeginSandiumAdDiagnostic(ctx);assert(first.epoch==1&&first.request==1);ReportSandiumAdDiagnostic(first,1,2,{true,false,true});assert(b.rows.size()==1&&b.rows[0][4]==5);
b.epoch=2;ReportSandiumAdDiagnostic(first,2,2,{});assert(b.rows.size()==1);auto second=BeginSandiumAdDiagnostic(ctx);assert(second.request==1&&second.epoch==2);
for(int i=0;i<520;i++){BeginSandiumAdDiagnostic(ctx);}assert(b.omitted==9);content::BrowserThread::ui=false;assert(BeginSandiumAdDiagnostic(ctx).epoch==0);ReportSandiumAdDiagnostic(second,1,2,{});assert(b.rows.size()==1);
content::BrowserThread::ui=true;content::RenderFrameHost::current=nullptr;ReportSandiumAdDiagnostic(second,1,2,{});assert(b.rows.size()==1);}
''')
   subprocess.run(['g++','-std=c++20','-Wall','-Wextra','-Werror',str(p),'-o',str(p.with_suffix(''))],check=True);subprocess.run([str(p.with_suffix(''))],check=True)
if __name__=='__main__':unittest.main()
