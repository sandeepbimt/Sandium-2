import importlib.util,pathlib,tempfile,subprocess,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('p',ROOT/'apply-popup.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Tests(unittest.TestCase):
 def test_probe_lifetime_and_outcomes(self):
  code=r'''#include <cstdint>
#include <functional>
#include <optional>
#include <vector>
#include <cassert>
#include <type_traits>
#include "bind_stateless_contract.inc"
namespace base {struct Delta{int64_t InMicroseconds(){return 1;}};struct TimeTicks{static TimeTicks Now(){return {};}Delta since_origin()const{return {};}friend Delta operator-(TimeTicks,TimeTicks){return {};}};
template<class T>struct WeakPtr{T* p=nullptr;WeakPtr()=default;WeakPtr(T* x):p(x){} explicit operator bool()const{return p!=nullptr;}T* get(){return p;}};
struct ScopedClosureRunner{std::function<void()> f;explicit ScopedClosureRunner(std::function<void()> x):f(x){}~ScopedClosureRunner(){f();}};template<class F>struct Traits {static constexpr bool is_stateless=std::is_empty_v<F>;};
template<class T>struct UnretainedWrapper {T* pointer;};
template<class T>UnretainedWrapper<T> Unretained(T* pointer){return {pointer};}
template<class F,class T>std::function<void()> BindOnce(F f,UnretainedWrapper<T> arg){static_assert(IsStateless<Traits<F>>::value);return [f,arg](){f(arg.pointer);};}
template<class F>std::function<void()> BindOnce(F f){static_assert(IsStateless<Traits<F>>::value);return f;}}
struct RenderFrameHostImpl;
struct WebContents{static WebContents* FromRenderFrameHost(RenderFrameHostImpl*){static WebContents w;return &w;}};
struct Client{int64_t epoch=1;std::vector<int> events;std::vector<double> statuses;
int64_t GetSandiumNavigationDiagnosticsEpoch(WebContents*){return epoch;}
void RecordSandiumNavigationDiagnosticForEpoch(WebContents*,int64_t e,int event,int64_t,int64_t,const std::vector<double>& v){if(e!=epoch||!e)return;events.push_back(event);if(event==20)statuses.push_back(v[1]);}} client;
struct Content{Client* browser(){return &client;}} content;Content* GetContentClient(){return &content;}
struct Params{bool started_with_transient_activation=true;int disposition=2;};
struct RenderFrameHostImpl{base::WeakPtr<RenderFrameHostImpl> GetWeakPtr(){return {this};}int64_t GetNavigationId(){return 42;}
void run(int mode){Params p;auto* params=&p;'''+m.PROBE+r'''
if(mode==1)sandium_record_popup(2.,0.,true);
if(mode==2){client.epoch=2;sandium_record_popup(2.,0.,true);}
if(mode==3)sandium_popup_weak={};
if(mode==4){sandium_record_popup(2.,0.,true);sandium_record_popup(3.,0.,false);}
if(mode==5)return;
}};
int main(){RenderFrameHostImpl r;r.run(0);assert(client.events.size()==2&&client.statuses.back()==-1);client.events.clear();r.run(1);assert(client.events.size()==2&&client.statuses.back()==2);client.events.clear();r.run(2);assert(client.events.size()==1);client.events.clear();client.epoch=1;r.run(3);assert(client.events.size()==1);client.events.clear();r.run(4);assert(client.events.size()==2&&client.statuses.back()==2);client.events.clear();r.run(5);assert(client.events.size()==2&&client.statuses.back()==-1);client.events.clear();client.epoch=0;r.run(0);assert(client.events.empty());}
'''
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d)/'t.cc';p.write_text(code)
   cmd=['g++','-std=c++20','-Wall','-Wextra','-Werror','-I',str(ROOT/'fixtures'),str(p),'-o',d+'/t']
   subprocess.run(cmd,check=True);subprocess.run([d+'/t'],check=True)
   # Mutation restores #1324's forbidden callback, proving the contract rejects it.
   old='sandium_popup_end.emplace(base::BindOnce([&]() { sandium_record_popup(-1., 1., false); }));'
   begin=code.index('    sandium_popup_end.emplace(base::BindOnce(')
   end=code.index('base::Unretained(&sandium_record_popup)));',begin)+len('base::Unretained(&sandium_record_popup)));')
   p.write_text(code[:begin]+old+code[end:])
   result=subprocess.run(cmd,capture_output=True,text=True)
   self.assertNotEqual(result.returncode,0)
   self.assertIn('Capturing lambdas and stateful functors',result.stderr)
if __name__=='__main__':unittest.main()
