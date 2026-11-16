"""Compile the actual Apply method with small API fakes; not full Blink rendering."""
import pathlib,subprocess,tempfile,unittest,json
ROOT=pathlib.Path(__file__).resolve().parents[1]
class DarkOffGate(unittest.TestCase):
 def test_off_on_retains_all_three_overrides(self):
  source=(ROOT/'native/sandium_element_colors.cc').read_text()
  begin=source.index('void SandiumElementColors::Apply(Element& element,')
  end=source.index('void SandiumElementColors::Trace',begin)
  code=source[begin:end]
  harness=r'''
#include <cassert>
#include <optional>
#include <vector>
using wtf_size_t=unsigned;
struct Settings{int flags=1;int GetSandiumDarkPageFlags()const{return flags;}};
struct Document{Settings* settings;Settings* GetSettings(){return settings;}};
struct Element{Document* document;Document& GetDocument(){return *document;}};
struct ComputedStyleBuilder{int writes=0;bool manual=false,palette=true,forced=true;
 void SetSandiumManualColorOverride(bool v){manual=v;}
 void SetSandiumPaletteEnabled(bool v){palette=v;}
 void SetColorSchemeForced(bool v){forced=v;}};
struct Entry{Element* element;std::optional<int> foreground,background,image_foreground;};
struct Entries:std::vector<Entry*>{void EraseAt(unsigned i){erase(begin()+i);}};
class SandiumElementColors{public:
 Entry* preview_=nullptr;Entries saved_;bool eligible=true;
 bool Eligible(Element&){return eligible;}
 void ApplyEntry(const Entry& entry,ComputedStyleBuilder& b){
  b.writes+=entry.foreground.has_value()+entry.background.has_value()+entry.image_foreground.has_value();}
 void Apply(Element&,ComputedStyleBuilder&);
};
'''+code+r'''
int main(){
 Settings settings;Document doc{&settings};Element target{&doc};
 Entry saved{&target,1,2,3},preview{&target,4,{}, {}};
 SandiumElementColors colors;colors.saved_.push_back(&saved);colors.preview_=&preview;
 ComputedStyleBuilder on;colors.Apply(target,on);assert(on.writes==4&&on.manual);
 settings.flags=0;ComputedStyleBuilder off;colors.Apply(target,off);
 assert(off.writes==0&&!off.manual);assert(colors.saved_.size()==1&&colors.preview_==&preview);
 settings.flags=1;ComputedStyleBuilder resumed;colors.Apply(target,resumed);
 assert(resumed.writes==4&&resumed.manual);
 settings.flags=-1;ComputedStyleBuilder unmanaged;colors.Apply(target,unmanaged);assert(unmanaged.writes==4);
 doc.settings=nullptr;ComputedStyleBuilder absent;colors.Apply(target,absent);assert(absent.writes==4);
 doc.settings=&settings;settings.flags=0;colors.eligible=false;
 ComputedStyleBuilder revoked;colors.Apply(target,revoked);
 assert(colors.saved_.empty()&&colors.preview_==nullptr&&revoked.writes==0);
}
'''
  with tempfile.TemporaryDirectory() as directory:
   root=pathlib.Path(directory);src=root/'gate.cc';exe=root/'gate';src.write_text(harness)
   result=subprocess.run(['c++','-std=c++20','-Wall','-Wextra','-Werror',str(src),'-o',str(exe)],text=True,capture_output=True)
   self.assertEqual(result.returncode,0,result.stderr)
   subprocess.run([str(exe)],check=True)
 def test_setting_invalidates_style_and_paint_without_clearing_store(self):
  patches=json.loads((ROOT.parent/'dark-pages/renderer/patches.json').read_text())
  setting=next(x['new'] for x in patches if 'name: "sandiumDarkPageFlags"' in x['new'])
  self.assertIn('invalidate: ["Style", "Paint"]',setting)
  source=(ROOT/'native/sandium_element_colors.cc').read_text()
  gate=source.split('// Explicit Dark Pages OFF',1)[1].split('// This runs after the palette policy',1)[0]
  self.assertIn('GetSandiumDarkPageFlags() == 0',gate)
  self.assertNotIn('Clear(',gate);self.assertNotIn('saved_.clear',gate)
if __name__=='__main__':unittest.main()
