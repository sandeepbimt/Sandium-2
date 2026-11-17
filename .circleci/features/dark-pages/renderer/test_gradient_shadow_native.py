#!/usr/bin/env python3
"""Compile extracted production helpers; no Android visual-result claim."""
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('gradient_patch', HERE / 'apply.py')
patcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patcher)
with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    shutil.copytree(HERE / 'fixtures', root / 'src')
    patcher.apply(root / 'src')
    paint = root / 'src/third_party/blink/renderer/core/paint'
    header = (paint / 'paint_auto_dark_mode.h').read_text()
    start = header.index('inline AutoDarkMode PaintAutoDarkMode(const ComputedStyle&')
    helper = header[start:header.index('\ninline AutoDarkMode PaintAutoDarkMode(DarkModeFilter', start)]
    source = (paint / 'paint_auto_dark_mode.cc').read_text()
    start = source.index('ImageAutoDarkMode ImageClassifierHelper::GetBackgroundImageAutoDarkMode(')
    gradient = source[start:source.index('\n// static', start)]
    box = (paint / 'box_painter_base.cc').read_text()
    assert box.count('GetBackgroundImageAutoDarkMode(') == 3
    shadow = 'PaintAutoDarkMode(style, DarkModeFilter::ElementRole::kBackground).enabled'
    assert 'return ' + shadow in box
    # Baseline image preservation remains intact for managed ON.
    assert 'style.SandiumManualColorOverride() || !style.ForceDark() || (flags >= 0 && (flags & 1) != 0)' in source
    code = r'''
#include <cassert>
struct DarkModeFilter {enum class ElementRole{kBackground};enum class ImageType{kPhoto,kIcon};};
struct AutoDarkMode {bool enabled;AutoDarkMode(DarkModeFilter::ElementRole,bool e,int=0):enabled(e){}static AutoDarkMode Disabled(DarkModeFilter::ElementRole r){return {r,false};}};
struct Color {int Rgb()const{return 0;}};
int GetCSSPropertyBackgroundColor(){return 0;}
struct ComputedStyle {bool managed,manual,stock;bool SandiumPaletteEnabled()const{return managed;}bool SandiumManualColorOverride()const{return manual;}bool ForceDark()const{return stock;}Color VisitedDependentColorFast(int)const{return {};}};
struct Image {bool gradient;bool IsGradientGeneratedImage()const{return gradient;}};
struct LocalFrame{};
namespace gfx {struct RectF{};}
struct ImageAutoDarkMode {DarkModeFilter::ElementRole role;bool enabled;DarkModeFilter::ImageType image_type;ImageAutoDarkMode(DarkModeFilter::ElementRole r,bool e,DarkModeFilter::ImageType t):role(r),enabled(e),image_type(t){} };
int delegates=0;
struct ImageClassifierHelper {
 static ImageAutoDarkMode GetImageAutoDarkMode(LocalFrame&,const ComputedStyle& s,const gfx::RectF&,const gfx::RectF&) {++delegates;return {DarkModeFilter::ElementRole::kBackground,!s.managed&&!s.manual&&s.stock,DarkModeFilter::ImageType::kIcon};}
 static ImageAutoDarkMode GetBackgroundImageAutoDarkMode(LocalFrame&,const ComputedStyle&,const Image&,const gfx::RectF&,const gfx::RectF&);
};
'''+helper+gradient+'\nbool shadow_enabled(const ComputedStyle& style){return '+shadow+';}\n'+r'''
int main(){
 LocalFrame frame;gfx::RectF rect;
 for(bool managed:{false,true}) for(bool manual:{false,true}) for(bool stock:{false,true}) {
  ComputedStyle style{managed,manual,stock};
  assert(shadow_enabled(style)==(!manual&&(managed||stock)));
  for(bool is_gradient:{false,true}) {
   Image image{is_gradient};delegates=0;
   auto mode=ImageClassifierHelper::GetBackgroundImageAutoDarkMode(frame,style,image,rect,rect);
   bool special=is_gradient&&managed&&!manual;
   assert(delegates==(special?0:1));
   assert(mode.enabled==(special||(!managed&&!manual&&stock)));
   if(special) assert(mode.image_type==DarkModeFilter::ImageType::kPhoto);
  }
 }
}
'''
    code = '#include <initializer_list>\n' + code
    (root/'test.cc').write_text(code)
    subprocess.run(['c++','-std=c++17','-Wall','-Wextra','-Werror',str(root/'test.cc'),'-o',str(root/'test')],check=True)
    subprocess.run([str(root/'test')],check=True)
print('SANDIUM_GRADIENT_SHADOW_NATIVE=PASS managed/off/unmanaged/manual/bitmap/gradient policy')
