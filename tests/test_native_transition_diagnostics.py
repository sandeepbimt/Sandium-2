import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
R=Path(__file__).resolve().parents[1]
def load(p):
 s=importlib.util.spec_from_file_location(p.stem,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
M=load(R/'experiments/native-transition-diagnostics/apply.py')
def sources():
 full=load(R/'.circleci/scripts/apply-sandium-page-transition-full.py')
 native=load(R/'.circleci/scripts/sandium-native-blur-source.py')
 back=load(R/'.circleci/scripts/apply-sandium-back-transition.py')
 s=native.implementation(full.transform_transition_cc((R/'tests/fixtures/ordinary-transition/blur_transition_animation_manager.cc').read_text()))
 t=(R/'tests/fixtures/back-transition'/M.BACK).read_text()
 for p,a,b in back.CHANGES:
  if p==M.BACK:t=back.transform(t,a,b)
 return {M.BLUR:s,M.BACK:t}
class Tests(unittest.TestCase):
 def test_full_composition_replay_and_no_behavior_edits(self):
  for p,s in sources().items():
   out=M.transform(p,s);self.assertEqual(M.transform(p,out),out)
   for path,old,new in reversed(M.CHANGES):
    if path==p:out=out.replace(new,old,1)
   self.assertEqual(out,s)
 def test_fail_closed(self):
  for p,s in sources().items():
   anchor=[a for path,a,b in M.CHANGES if path==p][-1]
   with self.assertRaises(ValueError):M.transform(p,s.replace(anchor,'BROKEN'))
 def test_actual_activation_time_and_native_ids(self):
  out=M.transform(M.BACK,sources()[M.BACK])
  self.assertEqual(out.count('activation_time.since_origin().InMicroseconds()'),2)
  self.assertIn('tracked_request_ ? tracked_request_->navigation_id : 0',out)
  self.assertNotIn('GetUniqueID()', ''.join(n for _,_,n in M.CHANGES))
 def test_compiled_payload_gate_and_bound(self):
  scalar=M.emit('wc',21,'nav',['1']*8)
  layer=M.layer('wc','nav','leaf',0,'2','view',0)
  code=r'''
#include <vector>
#include <cassert>
#include <cstdint>
namespace base {struct TimeTicks {static TimeTicks Now(){return {};} TimeTicks since_origin(){return {};} int64_t InMicroseconds(){return 123;}};}
struct Point {double x(){return 1;}double y(){return 2;}};
struct Size {int width(){return 100;}int height(){return 200;}};
struct Transform {bool IsIdentity(){return true;}};
namespace cc::slim {struct Layer {Layer* next=nullptr; Point position(){return {};}Size bounds(){return {};} Transform transform(){return {};}double opacity(){return 1;}Layer* parent(){return next;}};}
struct View {Size GetPhysicalBackingSize(){return {};}float GetDipScale(){return 2;}};
struct Client {bool enabled=false;int calls=0; std::vector<double> last;
 bool IsSandiumNavigationDiagnosticsEnabled(void*){return enabled;}
 void RecordSandiumNavigationDiagnostic(void*,int e,int64_t n,int64_t t,const std::vector<double>& v){assert(n==42&&t==123);assert(v.size()==(e==21?8:16));calls++;last=v;}
 Client* browser(){return this;}} client;
Client* GetContentClient(){return &client;}
void record(void* wc,int64_t nav,cc::slim::Layer* leaf,View* view){
'''+scalar+layer+r'''}
int main(){View view;cc::slim::Layer chain[20];for(int i=0;i<19;i++)chain[i].next=&chain[i+1];
record(nullptr,42,nullptr,nullptr);assert(client.calls==0);
client.enabled=true;record(nullptr,42,chain,&view);assert(client.calls==17);assert(client.last[14]==1);
}
'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'test.cc').write_text(code)
   subprocess.run(['g++','-std=c++17','-Wall','-Werror',str(p/'test.cc'),'-o',str(p/'test')],check=True)
   subprocess.run([str(p/'test')],check=True)
if __name__=='__main__':unittest.main()
