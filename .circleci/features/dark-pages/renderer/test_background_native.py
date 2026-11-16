"""Run actual patched canvas-background reporting with fake Blink APIs.

This validates policy/blending/control flow, not Skia colors or Android rendering.
"""
import json
from pathlib import Path
import subprocess
import tempfile

here = Path(__file__).resolve().parent
rel = 'third_party/blink/renderer/core/frame/local_frame_view.cc'
text = (here / 'fixtures' / rel).read_text()
for patch in json.loads((here / 'patches.json').read_text()):
    if patch['path'] == rel:
        assert text.count(patch['old']) == patch['count']
        text = text.replace(patch['old'], patch['new'])
code = text[text.index('Color LocalFrameView::DocumentBackgroundColor() {'):]
code = code[:code.index('\nvoid LocalFrameView::WillBeRemovedFromFrame()')]
source = r'''
#include <cassert>
#include <cmath>
struct Color {
 double value=255, alpha=1;
 Color Blend(Color over) const {
   double a=over.alpha+alpha*(1-over.alpha);
   return {a ? (over.value*over.alpha+value*alpha*(1-over.alpha))/a : 0,a};
 }
 Color toSkColor4f() const {return *this;}
 static Color FromSkColor4f(Color c) {return c;}
};
struct DarkModeFilter {
 enum class ElementRole {kBackground};
 int calls=0; Color last;
 Color InvertColorIfNeeded(Color c,ElementRole) {
   ++calls; last=c; if(c.value>128)c.value=255-c.value; return c;
 }
};
struct Style {
 bool policy=false,manual=false,forced=false,stock=false;
 bool SandiumPaletteEnabled()const{return policy;}
 bool SandiumManualColorOverride()const{return manual;}
 bool InForcedColorsMode()const{return forced;}
 bool ColorSchemeForced()const{return stock;}
};
int GetCSSPropertyBackgroundColor(){return 0;}
struct LayoutObject {
 Style style;Color color;
 Color ResolveColor(int)const{return color;}
 const Style& StyleRef()const{return style;}
};
constexpr int kPseudoIdBackdrop=1;
struct Element {
 LayoutObject* layout=nullptr;LayoutObject* backdrop=nullptr;
 LayoutObject* GetLayoutObject()const{return layout;}
 LayoutObject* PseudoElementLayoutObject(int)const{return backdrop;}
};
struct Document {
 Element* root=nullptr;Element* fullscreen=nullptr;bool printing=false,xr=false;
 Element* documentElement()const{return root;}
 bool Printing()const{return printing;}
 bool IsXrOverlay()const{return xr;}
};
struct Fullscreen {static Element* FullscreenElementFrom(Document& d){return d.fullscreen;}};
struct Frame {Document* doc;Document* GetDocument()const{return doc;}};
struct LocalFrameView {
 Frame* frame_;LayoutObject* layout;Color base;DarkModeFilter filter;
 Color BaseBackgroundColor()const{return base;}
 LayoutObject* GetLayoutView()const{return layout;}
 DarkModeFilter& EnsureDarkModeFilter(){return filter;}
 Color DocumentBackgroundColor();
};
'''+code+r'''
void expect(LocalFrameView& view,double value,int calls,double alpha=1){
 view.filter.calls=0;
 auto c=view.DocumentBackgroundColor();
 assert(std::abs(c.value-value)<1e-8);
 assert(std::abs(c.alpha-alpha)<1e-8);
 assert(view.filter.calls==calls);
}
int main(){
 LayoutObject canvas,root;Element html{&root};Document doc{&html};Frame frame{&doc};
 LocalFrameView view{&frame,&canvas,{}, {}};
 // Synthetic LayoutView has no policy; the real root is authoritative.
 root.style.policy=true;expect(view,0,1);
 assert(canvas.color.value==255 && view.base.value==255); // no paint-input mutation
 // Already dark stays dark; the filter decides, not a flattened palette.
 canvas.color={20,1};expect(view,20,1);
 // Transparent/partial author canvas is blended BEFORE one native transform.
 canvas.color={200,.5};expect(view,27.5,1);
 assert(view.filter.last.value==227.5 && view.filter.last.alpha==1);
 canvas.color={77,0};expect(view,0,1);
 // OFF / unmanaged / manual / printing / forced colors leave original reporting.
 canvas.color={200,1};root.style.policy=false;expect(view,200,0);
 root.style.policy=true;root.style.manual=true;expect(view,200,0);root.style.manual=false;
 root.style.forced=true;expect(view,200,0);root.style.forced=false;
 doc.printing=true;expect(view,200,0);doc.printing=false;
 // Null document/root/layout remains safe and does not invent eligibility.
 doc.root=nullptr;expect(view,200,0);doc.root=&html;
 html.layout=nullptr;expect(view,200,0);html.layout=&root;
 frame.doc=nullptr;expect(view,200,0);frame.doc=&doc;
 view.layout=nullptr;expect(view,255,0);view.layout=&canvas;
 // Upstream legacy stock behavior is retained when Sandium does not apply.
 root.style.policy=false;canvas.style.stock=true;expect(view,55,1);
 canvas.color={200,.5};expect(view,155,1);canvas.style.stock=false;
 // When both are marked, never transform twice.
 root.style.policy=true;canvas.style.stock=true;expect(view,27.5,1);canvas.style.stock=false;
 // Fullscreen backdrop must use its own policy, not the root's.
 LayoutObject backdrop;backdrop.color={210,1};Element full{&root,&backdrop};doc.fullscreen=&full;
 expect(view,210,0);backdrop.style.policy=true;expect(view,45,1);
 backdrop.style.manual=true;expect(view,210,0);backdrop.style.manual=false;
 // XR uses the fullscreen element directly and preserves alpha, without base blend.
 LayoutObject xr;xr.style.policy=true;xr.color={200,.5};full.layout=&xr;doc.xr=true;
 expect(view,55,1,.5);
}
'''
with tempfile.TemporaryDirectory() as tmp:
    src=Path(tmp)/'background.cc';exe=Path(tmp)/'background'
    src.write_text(source)
    subprocess.run(['c++','-std=c++20','-Wall','-Wextra','-Werror',str(src),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
print('Actual DocumentBackgroundColor policy/blending fake-API tests pass; NOT Blink/device verification.')
