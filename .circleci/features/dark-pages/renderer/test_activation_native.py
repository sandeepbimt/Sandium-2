"""Compile actual activation apply blocks with fake live Settings callbacks."""
import json
from pathlib import Path
import subprocess
import tempfile
here=Path(__file__).resolve().parent
patches=json.loads((here/'patches.json').read_text())
bf=next(p['new'] for p in patches if p['old'].startswith('  bool restoring_from_bfcache ='))
bf=bf[bf.index('  if (restoring_from_bfcache'):]
pr=next(p['new'] for p in patches if p['old'].startswith('  TRACE_EVENT0("navigation", "WebViewImpl::ActivatePrerenderedPage")'))
pr=pr[pr.index('  const int sandium_policy'):pr.index('  // From here')]
src=r'''
#include <cassert>
#define TRACE_EVENT1(...) ((void)0)
struct Settings {int flag=-1,invalidations=0;bool native_force=true;int native_scheme=17;void SetSandiumDarkPageFlags(int p){if(flag!=p){flag=p;++invalidations;}}};
struct Page {Settings s;Settings& GetSettings(){return s;}};
struct Params {int sandium_dark_page_flags=-1;};
struct View {Page p;Page* GetPage(){return &p;}void BF(bool restoring_from_bfcache,Params* page_restore_params){Page* page=&p;
'''+bf+r'''
}void PR(Params* prerender_page_activation_params){
'''+pr+r'''
}};
int main(){
 View v;Params on{1},off{0},unmanaged{-1};
 v.BF(false,&on);assert(v.p.s.flag==-1&&v.p.s.invalidations==0);
 v.BF(true,nullptr);assert(v.p.s.flag==-1);
 v.BF(true,&on);assert(v.p.s.flag==1&&v.p.s.invalidations==1);
 v.BF(true,&on);assert(v.p.s.invalidations==1);
 v.BF(true,&off);assert(v.p.s.flag==0&&v.p.s.invalidations==2);
 v.BF(true,&unmanaged);assert(v.p.s.flag==-1);
 v.PR(&on);assert(v.p.s.flag==1);v.PR(&off);assert(v.p.s.flag==0);
 v.PR(&unmanaged);assert(v.p.s.flag==-1);
 assert(v.p.s.native_force&&v.p.s.native_scheme==17);
 View views[3];for(auto& item:views)item.PR(&on);for(auto& item:views)assert(item.p.s.flag==1);
}
'''
with tempfile.TemporaryDirectory() as temp:
 source=Path(temp)/'test.cc';exe=Path(temp)/'test';source.write_text(src)
 subprocess.run(['c++','-std=c++20','-Wall','-Wextra','-Werror',str(source),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)
print('Actual activation blocks compile/pass fake live-settings tests; NOT browser BFCache/prerender tests.')
