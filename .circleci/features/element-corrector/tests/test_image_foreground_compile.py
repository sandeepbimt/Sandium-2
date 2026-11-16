#!/usr/bin/env python3
"""Pinned API syntax + actual image wrapper with narrow paint fakes, not Blink rendering."""
import hashlib,importlib.util,pathlib,re,shutil,subprocess,tempfile,unittest
FEATURE=pathlib.Path(__file__).resolve().parents[1]
REPO=FEATURE.parents[2]
spec=importlib.util.spec_from_file_location('draft',FEATURE/'apply-native-draft.py')
draft=importlib.util.module_from_spec(spec);spec.loader.exec_module(draft)
class ImageForeground(unittest.TestCase):
 def test_pinned_blend_api(self):
  header=(FEATURE/'tests/fixtures/color_filter.h').read_bytes()
  self.assertEqual(hashlib.sha256(header).hexdigest(),'9f700fe8207e2b911614fb66f336742595fb57549288ea63c3264ec959089c8a')
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d)
   files={'cc/paint/paint_export.h':'#define CC_PAINT_EXPORT\n',
    'third_party/skia/include/core/SkBlendMode.h':'enum class SkBlendMode { kSrcIn };\n',
    'third_party/skia/include/core/SkColor.h':'#include <cstdint>\nstruct SkColor4f {static SkColor4f FromColor(uint32_t);};\n',
    'third_party/skia/include/core/SkRefCnt.h':'#include <cstddef>\nclass SkRefCnt {public:virtual ~SkRefCnt()=default;}; template<class T> class sk_sp {};\n'}
   for path,text in files.items():
    p=root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
   (root/'cc/paint/color_filter.h').write_bytes(header)
   p=root/'call.cc';p.write_text('#include "cc/paint/color_filter.h"\nvoid f(unsigned rgb){auto filter=cc::ColorFilter::MakeBlend(SkColor4f::FromColor(rgb), SkBlendMode::kSrcIn);(void)filter;}')
   r=subprocess.run(['c++','-std=c++20','-Wall','-Wextra','-Werror','-fsyntax-only','-I'+str(root),str(p)],capture_output=True,text=True)
   self.assertEqual(r.returncode,0,r.stderr)
 def test_actual_wrapper_and_style_scope(self):
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d)
   shutil.copytree(REPO/'native-pinned/third_party',root/'third_party')
   p=root/'third_party/blink/renderer/core/css/resolver/style_adjuster.cc'
   p.write_text(p.read_text().replace('\n}\n\nbool StyleAdjuster::IsCacheCompatible(', '\n  ApplySandiumPaintPolicy(builder, element, element_or_pseudo_element, parent_style);\n}\n\nbool StyleAdjuster::IsCacheCompatible(',1))
   edits=draft.compose(root)
   paint=edits[root/'third_party/blink/renderer/core/paint/image_painter.cc']
   wrapper=paint[paint.index('  // Explicit Element Color Correction only'):paint.index('  context.DrawImage(')]
   tail='  if (image_foreground) context.EndLayer();'
   self.assertIn(tail,paint)
   fields=edits[root/'third_party/blink/renderer/core/style/computed_style_extra_fields.json5']
   self.assertRegex(fields,r'name: "SandiumImageForeground",[\s\S]*?reset_on_new_style: true,[\s\S]*?inherited: false,[\s\S]*?invalidate: \["paint"\]')
   native=edits[root/'third_party/blink/renderer/core/dom/sandium_element_colors.cc']
   self.assertEqual(native.count('(property == 2 && !element.HasTagName(html_names::kImgTag))'),2)
   self.assertIn('if (has_surface_override) {\n    builder.SetSandiumManualColorOverride(true);',native)
   source=r'''
#include <cassert>
#include <vector>
struct SkColor4f {unsigned rgb;static SkColor4f FromColor(unsigned rgb){return {rgb};}};
enum class SkBlendMode{kSrcIn};
namespace cc {struct ColorFilter{unsigned rgb;static ColorFilter MakeBlend(SkColor4f c,SkBlendMode){return {c.rgb};}};}
struct ImageAutoDarkMode {bool enabled=true;static ImageAutoDarkMode Disabled(){return {false};}};
struct Style{unsigned rgb;unsigned SandiumImageForeground()const{return rgb;}};
struct Layout{Style style;const Style& StyleRef()const{return style;}};
struct Context{std::vector<int> calls;unsigned rgb=0;void BeginLayer(cc::ColorFilter f){rgb=f.rgb;calls.push_back(1);}void DrawImage(){calls.push_back(2);}void EndLayer(){calls.push_back(3);}};
void paint(Context& context,bool image_element,Layout layout_image_,ImageAutoDarkMode& image_auto_dark_mode){
'''+wrapper+'context.DrawImage();\n'+tail+r'''
}
int main(){for(bool img:{false,true})for(unsigned rgb:{0u,0xff000000u,0xffeeeeeeu,0xff123456u}){
 Context c;ImageAutoDarkMode mode;paint(c,img,{{rgb}},mode);
 const bool active=img&&rgb;
 assert(c.calls==(active?std::vector<int>{1,2,3}:std::vector<int>{2}));
 assert(mode.enabled==!active);assert(c.rgb==(active?rgb:0));
}}
'''
   p=root/'wrapper.cc';p.write_text(source);exe=root/'wrapper'
   r=subprocess.run(['c++','-std=c++20','-Wall','-Wextra','-Werror',str(p),'-o',str(exe)],capture_output=True,text=True)
   self.assertEqual(r.returncode,0,r.stderr);subprocess.run([str(exe)],check=True)
if __name__=='__main__':unittest.main()
