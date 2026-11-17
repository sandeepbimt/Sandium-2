import importlib.util,pathlib,subprocess,tempfile,unittest
P=pathlib.Path;HERE=P(__file__).parent
s=importlib.util.spec_from_file_location('load',HERE/'load_snapshot.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)

def pinned(path):return (HERE/'fixtures'/path).read_text()
class Tests(unittest.TestCase):
 def test_pinned_replay_failure_and_resources_only(self):
  h=pinned(m.HEADER);s=pinned(m.SOURCE);out=m.source(s)
  self.assertEqual(m.header(m.header(h)),m.header(h));self.assertEqual(m.source(out),out)
  self.assertIn('sandium_load_result_[sandium_lane] = success ? 1 : 0;',out)
  self.assertLess(out.index('sandium_load_result_[sandium_lane] = static_cast<int>(load_result);'),out.index('if (load_result != FilterListLoadResult::kResourcesOnly)'))
  self.assertIn('kLoaded,\n    kFailed,\n    kResourcesOnly,',h)
  with self.assertRaises(ValueError):m.source('unexpected source')
 def test_actual_state_updates_and_snapshot(self):
  source=m.source(pinned(m.SOURCE));start=source.index('AdBlockService::SandiumDiagnosticLoadSnapshot');end=source.index('void AdBlockService::OnDATLoaded',start);getter=source[start:end]
  dat=source[source.index('  const size_t sandium_lane = is_default_engine ? 0 : 2;'):];dat=dat[:dat.index('  if (is_default_engine)')]
  eng=source[source.index('  const size_t sandium_lane = is_default_engine ? 1 : 3;'):];eng=eng[:eng.index('\n\n')]
  with tempfile.TemporaryDirectory() as d:
   p=P(d)/'t.cc';p.write_text('''#include <array>
#include <cstdint>
#include <cstddef>
#include <cassert>
#define DCHECK_CALLED_ON_VALID_SEQUENCE(x) ((void)0)
class AdBlockService {public:using SandiumDiagnosticLoadSnapshot=std::array<std::array<int64_t,6>,4>;std::array<int,4> sandium_load_result_{{-1,-1,-1,-1}};std::array<int64_t,4> sandium_load_sequence_{};int64_t sandium_next_load_sequence_=0;SandiumDiagnosticLoadSnapshot GetSandiumDiagnosticLoadSnapshot() const;
void dat(bool is_default_engine,bool success){'''+dat+'''}void list(bool is_default_engine,int load_result){'''+eng+'''}};
'''+getter+'''int main(){AdBlockService s;auto a=s.GetSandiumDiagnosticLoadSnapshot();for(auto row:a){assert(row[2]==-1&&row[3]==0&&row[4]==-1&&row[5]==1);}s.dat(true,false);s.list(true,0);s.list(false,1);s.list(false,2);a=s.GetSandiumDiagnosticLoadSnapshot();assert(a[0][2]==0&&a[0][3]==1);assert(a[1][2]==0&&a[1][3]==2);assert(a[3][2]==2&&a[3][3]==4);s.dat(false,true);a=s.GetSandiumDiagnosticLoadSnapshot();assert(a[2][2]==1&&a[2][3]==5);}
''')
   subprocess.run(['g++','-std=c++20','-Wall','-Wextra','-Werror',str(p),'-o',str(p.with_suffix(''))],check=True);subprocess.run([str(p.with_suffix(''))],check=True)
if __name__=='__main__':unittest.main()
