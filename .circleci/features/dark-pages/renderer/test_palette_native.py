"""Compile actual palette color helper against Color API fake; no Blink compile."""
import json
from pathlib import Path
import subprocess
import tempfile
p=Path(__file__).resolve().parent
s=next(x['new'] for x in json.loads((p/'patches.json').read_text()) if x['old']=='SkColor4f DarkModeColor(GraphicsContext& context,')
s=s[s.index('SkColor4f SandiumPaletteColor'):s.index('SkColor4f DarkModeColor')]
stub=r'''
#include <algorithm>
#include <cassert>
#include <cmath>
struct SkColor4f {float fR=0,fG=0,fB=0,fA=1;bool operator==(const SkColor4f&)const=default;};
struct DarkModeFilter {enum class ElementRole {kForeground,kListSymbol,kBackground,kSVG,kBorder,kSelection};};
'''
main=r'''
float linear(float v){return v<=0.04045f?v/12.92f:std::pow((v+0.055f)/1.055f,2.4f);}
float luma(SkColor4f c){return 0.2126f*linear(c.fR)+0.7152f*linear(c.fG)+0.0722f*linear(c.fB);}
float contrast(SkColor4f a,SkColor4f b){float x=luma(a),y=luma(b);return (std::max(x,y)+0.05f)/(std::min(x,y)+0.05f);}
int main(){
 using Role=DarkModeFilter::ElementRole;
 SkColor4f opaque{1,1,1,1},dark{26.f/255.f,26.f/255.f,26.f/255.f,1},text{232.f/255.f,232.f/255.f,232.f/255.f,1};
 assert(contrast(SandiumPaletteColor(opaque,Role::kBorder),dark)>=3.f);
 assert(contrast(text,SandiumPaletteColor(opaque,Role::kSelection))>=4.5f);
 SkColor4f minimum_text{180.f/255.f,180.f/255.f,180.f/255.f,1};
 assert(contrast(minimum_text,SandiumPaletteColor(opaque,Role::kSelection))>=4.5f);
 for(int a=0;a<=100;a++){
  SkColor4f translucent{1,1,1,a/100.f};auto mapped=SandiumPaletteColor(translucent,Role::kBackground);
  SkColor4f composite{mapped.fR*mapped.fA+dark.fR*(1-mapped.fA),mapped.fG*mapped.fA+dark.fG*(1-mapped.fA),mapped.fB*mapped.fA+dark.fB*(1-mapped.fA),1};
  assert(contrast(text,composite)>=4.5f);
 }
 for(int r=0;r<=255;r+=5)for(int g=0;g<=255;g+=5)for(int b=0;b<=255;b+=5){
  SkColor4f c{r/255.f,g/255.f,b/255.f,1.f};
  auto fg=SandiumPaletteColor(c,Role::kForeground),bg=SandiumPaletteColor(c,Role::kBackground);
  assert(std::min({fg.fR,fg.fG,fg.fB})>=180.f/255.f);assert(std::max({bg.fR,bg.fG,bg.fB})<=26.f/255.f);
  assert(fg==SandiumPaletteColor(fg,Role::kForeground));assert(bg==SandiumPaletteColor(bg,Role::kBackground));
  assert(c==SandiumPaletteColor(c,Role::kSVG));
  auto border=SandiumPaletteColor(c,Role::kBorder),selection=SandiumPaletteColor(c,Role::kSelection);
  assert(std::min({border.fR,border.fG,border.fB})>=112.f/255.f);
  assert(contrast(border,dark)>=3.f);
  assert(contrast(fg,selection)>=4.5f);
  if(c.fR>c.fG+24.f/255.f && c.fR>c.fB+24.f/255.f)assert(border.fR>border.fG && border.fR>border.fB);
  if(c.fG>c.fR+24.f/255.f && c.fG>c.fB+24.f/255.f)assert(border.fG>border.fR && border.fG>border.fB);
  assert(selection.fB>selection.fR && selection.fB>26.f/255.f);
  c.fA=0;assert(c==SandiumPaletteColor(c,Role::kForeground));assert(c==SandiumPaletteColor(c,Role::kBackground));
  c.fA=0.4f;assert(SandiumPaletteColor(c,Role::kForeground).fA==c.fA);assert(SandiumPaletteColor(c,Role::kBackground).fA==c.fA);
 }
}
'''
with tempfile.TemporaryDirectory() as t:
 src=Path(t)/'test.cc';exe=Path(t)/'test';src.write_text(stub+s+main)
 subprocess.run(['c++','-std=c++20','-Wall','-Wextra','-Werror',str(src),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)
print('Actual color helper compiled; 140608 sampled colors checked for bounds/idempotence/alpha. NOT Blink rendering test.')
