import importlib.util,pathlib,subprocess,tempfile,unittest
P=pathlib.Path;HERE=P(__file__).parent;s=importlib.util.spec_from_file_location('domain',HERE/'domain.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)

def pinned(path):return (HERE/'fixtures'/path).read_text()
class Tests(unittest.TestCase):
 def test_exact_source_outcomes_replay(self):
  for p,f in [(m.HEADER,m.header),(m.SOURCE,m.source)]:
   out=f(pinned(p));self.assertEqual(f(out),out)
  for value in ('GetNavigationId()', 'sandium_diagnostic_epoch_', 'RecordSandiumNavigationDiagnosticForEpoch'):
   self.assertIn(value,m.REPORT)
  self.assertNotIn('GetURL',m.REPORT)
  out=m.source(pinned(m.SOURCE))
  for phase in (15,16,17,20,30,31,32):self.assertIn('ReportSandiumDomainDiagnostic('+str(phase),out)
  self.assertIn('is_1pes_enabled ? 18 : 19',out)
 def test_report_actual_body_epoch_and_id(self):
  with tempfile.TemporaryDirectory() as d:
   p=P(d)/'t.cc';p.write_text('''#include <cstdint>
#include <vector>
#include <cassert>
namespace base{struct Delta{int64_t x;int64_t InMicroseconds(){return x;}};struct TimeTicks{int64_t x=10;static TimeTicks Now(){return {20};}Delta since_origin()const{return {x};}friend Delta operator-(TimeTicks a,TimeTicks b){return {a.x-b.x};}};}
namespace blink::mojom{enum class ResourceType{kMainFrame=0};}
namespace content{struct WebContents{bool priv=false;};struct Handle{WebContents wc;WebContents* GetWebContents(){return &wc;}int64_t GetNavigationId(){return 123;}};struct Browser{int calls=0;int64_t lastid=0;std::vector<double> row;void RecordSandiumNavigationDiagnosticForEpoch(WebContents* w,int64_t epoch,int code,int64_t id,int64_t,const std::vector<double>& v){if(w->priv||epoch!=5)return;assert(code==11);calls++;lastid=id;row=v;}};struct Client{Browser b;Browser* browser(){return &b;}};Client client;Client* GetContentClient(){return &client;}}
class DomainBlockNavigationThrottle {public:int64_t sandium_diagnostic_epoch_=0;base::TimeTicks sandium_diagnostic_started_;content::Handle h;content::Handle* navigation_handle(){return &h;}void ReportSandiumDomainDiagnostic(int,bool,bool);};
'''+m.REPORT+'''int main(){DomainBlockNavigationThrottle t;auto& b=content::client.b;t.ReportSandiumDomainDiagnostic(15,true,false);assert(b.calls==0);t.sandium_diagnostic_epoch_=5;t.ReportSandiumDomainDiagnostic(15,true,false);assert(b.calls==1&&b.lastid==123&&b.row[1]==15&&b.row[4]==1&&b.row[7]==10);t.h.wc.priv=true;t.ReportSandiumDomainDiagnostic(20,false,true);assert(b.calls==1);t.h.wc.priv=false;t.sandium_diagnostic_epoch_=4;t.ReportSandiumDomainDiagnostic(20,false,true);assert(b.calls==1);}
''')
   subprocess.run(['g++','-std=c++20','-Wall','-Wextra','-Werror',str(p),'-o',str(p.with_suffix(''))],check=True);subprocess.run([str(p.with_suffix(''))],check=True)
if __name__=='__main__':unittest.main()
