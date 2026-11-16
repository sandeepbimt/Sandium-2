"""Actual paint wrapper compiled against narrow style/draw API fakes."""
from pathlib import Path
import json
import subprocess
import tempfile
here=Path(__file__).resolve().parent
body=next(x['new'] for x in json.loads((here/'patches.json').read_text()) if x['path'].endswith('paint_auto_dark_mode.h'))
source=r'''
#include <cassert>
struct DarkModeFilter{enum class ElementRole{kForeground,kBackground,kSVG};};
struct AutoDarkMode{DarkModeFilter::ElementRole role;bool enabled;int contrast_color;AutoDarkMode(DarkModeFilter::ElementRole r,bool e,int c=0):role(r),enabled(e),contrast_color(c){}static AutoDarkMode Disabled(DarkModeFilter::ElementRole r){return {r,false};}};
int GetCSSPropertyBackgroundColor(){return 0;}
struct Color{int Rgb()const{return 0;}};
struct ComputedStyle{bool manual,custom,stock;bool SandiumManualColorOverride()const{return manual;}bool SandiumPaletteEnabled()const{return custom;}bool ForceDark()const{return stock;}Color VisitedDependentColorFast(int)const{return {};}};
AutoDarkMode PaintAutoDarkMode(const ComputedStyle& style,DarkModeFilter::ElementRole role){
'''+body+r'''
}
int main(){for(bool manual:{false,true})for(bool custom:{false,true})for(bool stock:{false,true}){
 ComputedStyle s{manual,custom,stock};auto m=PaintAutoDarkMode(s,DarkModeFilter::ElementRole::kForeground);
 if(manual){assert(!m.enabled);}else{assert(m.enabled==(custom||stock));}
}}
'''
source='#include <initializer_list>\n'+source
with tempfile.TemporaryDirectory() as t:
 src=Path(t)/'test.cc';exe=Path(t)/'test';src.write_text(source)
 subprocess.run(['c++','-std=c++20','-Wall','-Wextra','-Werror',str(src),'-o',str(exe)],check=True);subprocess.run([str(exe)],check=True)
print('Actual paint wrapper manual/custom/stock combinations pass native fake-API test; NOT Blink rendering.')
