"""Compile actual style policy with protected-builder API fakes, not Blink."""
import json
from pathlib import Path
import subprocess
import tempfile
here=Path(__file__).resolve().parent
s=next(x['new'] for x in json.loads((here/'patches.json').read_text()) if x['old']=='void StyleAdjuster::RunUncacheableStyleAdjustment(')
code=s[s.index('void StyleAdjuster::ApplySandiumPaintPolicy('):s.index('void StyleAdjuster::RunUncacheableStyleAdjustment(')]
source=r'''
#include <cassert>
class StyleAdjuster;
enum PseudoId{kPseudoIdNone,kPseudoIdBefore};
struct Settings{int flags=-1;int GetSandiumDarkPageFlags()const{return flags;}};
struct Element;
struct Document{Settings* settings;Element* root=nullptr;bool printing=false;const Settings* GetSettings()const{return settings;}Element* documentElement(){return root;}bool Printing()const{return printing;}};
struct Element{Document* doc;bool svg=false;Document& GetDocument(){return *doc;}bool IsSVGElement()const{return svg;}};
struct Layer{bool image=false;bool AnyLayerHasImage()const{return image;}};
struct BuilderBase{Layer layer;protected:const Layer& BackgroundInternal()const{return layer;}};
struct ComputedStyleBuilder:BuilderBase{friend class StyleAdjuster;bool manual=false,palette=false,stock=true,forced=false;PseudoId pseudo=kPseudoIdNone;
 bool SandiumManualColorOverride()const{return manual;}void SetColorSchemeForced(bool b){stock=b;}void SetSandiumPaletteEnabled(bool b){palette=b;}bool InForcedColorsMode()const{return forced;}PseudoId StyleType()const{return pseudo;}};
struct ComputedStyle{bool enabled=false;bool SandiumPaletteEnabled()const{return enabled;}};
class StyleAdjuster{public:static void ApplySandiumPaintPolicy(ComputedStyleBuilder&,Element&,const Element*,const ComputedStyle*);};
'''+code+r'''
int main(){
 Settings settings{1};Document doc{&settings};Element root{&doc},child{&doc};doc.root=&root;ComputedStyle parent{true};
 ComputedStyleBuilder b;StyleAdjuster::ApplySandiumPaintPolicy(b,root,&root,nullptr);assert(b.palette&&!b.stock);
 b={};StyleAdjuster::ApplySandiumPaintPolicy(b,child,&child,&parent);assert(b.palette&&!b.stock);
 b={};StyleAdjuster::ApplySandiumPaintPolicy(b,child,nullptr,&parent);assert(b.palette&&!b.stock);
 b={};b.layer.image=true;StyleAdjuster::ApplySandiumPaintPolicy(b,child,&child,&parent);assert(b.palette&&!b.stock);
 b={};child.svg=true;StyleAdjuster::ApplySandiumPaintPolicy(b,child,&child,&parent);assert(b.palette&&!b.stock);child.svg=false;
 b={};b.pseudo=kPseudoIdBefore;ComputedStyle excluded{false};StyleAdjuster::ApplySandiumPaintPolicy(b,root,&root,&excluded);assert(b.palette);
 b={};settings.flags=0;StyleAdjuster::ApplySandiumPaintPolicy(b,root,&root,nullptr);assert(!b.palette&&!b.stock);
 b={};settings.flags=-1;StyleAdjuster::ApplySandiumPaintPolicy(b,root,&root,nullptr);assert(!b.palette&&b.stock);
 b={};b.manual=true;StyleAdjuster::ApplySandiumPaintPolicy(b,root,&root,nullptr);assert(!b.palette&&!b.stock);
 b={};settings.flags=1;b.forced=true;StyleAdjuster::ApplySandiumPaintPolicy(b,root,&root,nullptr);assert(!b.palette&&b.stock);
 b={};doc.printing=true;StyleAdjuster::ApplySandiumPaintPolicy(b,root,&root,nullptr);assert(!b.palette&&b.stock);
}
'''
with tempfile.TemporaryDirectory() as t:
 src=Path(t)/'test.cc';exe=Path(t)/'test';src.write_text(source)
 subprocess.run(['c++','-std=c++20','-Wall','-Wextra','-Werror',str(src),'-o',str(exe)],check=True);subprocess.run([str(exe)],check=True)
print('Actual style helper protected access/policy combinations compile/pass fake APIs. NOT Blink compile.')
