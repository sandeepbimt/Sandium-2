#!/usr/bin/env python3
"""Compose renderer/browser selection wiring. Offline only pending Android/review."""
import pathlib,argparse,re
ROOT=pathlib.Path(__file__).resolve().parent

def once(s,old,new):
 if new in s:return s
 if s.count(old)!=1:raise ValueError('Pinned anchor mismatch: '+old[:80])
 return s.replace(old,new,1)
def compose(root):
 edits={}
 def change(name,fn):
  p=root/name;edits[p]=fn(p.read_text())
 common='brave/components/cosmetic_filters/common/cosmetic_filters.mojom'
 change(common,lambda s:once(s,'interface CosmeticFiltersHandler {','interface CosmeticFiltersHandler {\n  OfferElementColorSelection(mojo_base.mojom.UnguessableToken session, uint64 node, mojo_base.mojom.DictionaryValue descriptor) => (bool accepted);'))
 hdr='brave/components/cosmetic_filters/renderer/cosmetic_filters_js_handler.h'
 change(hdr,lambda s:once(once(s,'namespace cosmetic_filters {','namespace cosmetic_filters {\nclass ElementColorRenderer;'),
   '  bool generichide_ = false;','  std::unique_ptr<ElementColorRenderer> color_renderer_;\n  bool generichide_ = false;'))
 src='brave/components/cosmetic_filters/renderer/cosmetic_filters_js_handler.cc'
 def handler(s):
  inc='#include "brave/components/cosmetic_filters/renderer/cosmetic_filters_js_handler.h"'
  s=once(s,inc,inc+'\n#include "brave/components/cosmetic_filters/renderer/element_color_renderer.h"')
  anchor='      v8_value_converter_(content::V8ValueConverter::Create()) {\n  EnsureConnected();'
  s=once(s,anchor,anchor+'\n  color_renderer_=std::make_unique<ElementColorRenderer>(render_frame,isolated_world_id);')
  anchor='void CosmeticFiltersJSHandler::BindFunctionsToObject(\n    v8::Isolate* isolate,\n    v8::Local<v8::Object> javascript_object) {'
  return once(s,anchor,anchor+'\n  color_renderer_->BindWorker(isolate,javascript_object);')
 change(src,handler)
 change('brave/components/cosmetic_filters/renderer/BUILD.gn',lambda s:once(s,'  sources = [','  sources = [\n    "element_color_renderer.cc",\n    "element_color_renderer.h",\n    "element_color_picker_script.h",'))
 h='brave/browser/cosmetic_filters/cosmetic_filters_tab_helper.h'
 change(h,lambda s:once(s,'  void AddSiteCosmeticFilter(const std::string& filter) override;',
   '  void OfferElementColorSelection(const base::UnguessableToken&,uint64_t,base::DictValue,OfferElementColorSelectionCallback) override;\n  void AddSiteCosmeticFilter(const std::string& filter) override;'))
 def helper(s):
  inc='#include "brave/browser/cosmetic_filters/cosmetic_filters_tab_helper.h"'
  s=once(s,inc,inc+'\n#include "build/build_config.h"\n#if BUILDFLAG(IS_ANDROID)\n#include "brave/browser/sandium/element_color_session.h"\n#endif')
  anchor='void CosmeticFiltersTabHelper::AddSiteCosmeticFilter('
  method='''void CosmeticFiltersTabHelper::OfferElementColorSelection(const base::UnguessableToken& token,
    uint64_t node,base::DictValue descriptor,OfferElementColorSelectionCallback result) {
#if BUILDFLAG(IS_ANDROID)
  auto* session=sandium::ElementColorSession::FromWebContents(&GetWebContents());
  bool accepted=session && session->OfferSelection(receivers_.CurrentTargetFrame(),token,node,descriptor);
  std::move(result).Run(accepted);
#else
  std::move(result).Run(false);
#endif
}

'''+anchor
  return once(s,anchor,method)
 change('brave/browser/cosmetic_filters/cosmetic_filters_tab_helper.cc',helper)
 def tabs(s):
  inc='#include "brave/browser/brave_tab_helpers.h"'
  s=once(s,inc,inc+'\n#include "build/build_config.h"\n#if BUILDFLAG(IS_ANDROID)\n#include "brave/browser/sandium/element_color_session.h"\n#endif')
  a='void AttachTabHelpers(content::WebContents* web_contents) {'
  return once(s,a,a+'\n#if BUILDFLAG(IS_ANDROID)\n  sandium::ElementColorSession::GetOrCreate(web_contents);\n#endif')
 change('brave/browser/brave_tab_helpers.cc',tabs)
 for name in ['element_color_renderer.cc','element_color_renderer.h']:
  edits[root/'brave/components/cosmetic_filters/renderer'/name]=(ROOT/'native'/name).read_text()
 for name in ['sandium_element_colors_utils.cc','sandium_element_colors_utils.h']:
  edits[root/'brave/browser/android/cosmetic_filters'/name]=(ROOT/'native'/name).read_text()
 core='(()=>{\n'+re.sub(r'\bexport (?=function)', '',(ROOT/'renderer/corrector.mjs').read_text())+'\n'
 picker=core+(ROOT/'renderer/picker-entry.js').read_text()+'\n})();'
 header='#ifndef SANDIUM_ELEMENT_PICKER_SCRIPT_H_\n#define SANDIUM_ELEMENT_PICKER_SCRIPT_H_\nnamespace cosmetic_filters {\n'
 for name,value in [('kSandiumElementCoreScript',core),('kSandiumElementPickerScript',picker)]:
  if ')SANDIUM"' in value:raise ValueError('Raw string delimiter collision')
  header+=f'inline constexpr char {name}[] = R"SANDIUM({value})SANDIUM";\n'
 header+='}\n#endif\n'
 edits[root/'brave/components/cosmetic_filters/renderer/element_color_picker_script.h']=header
 return edits
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('source_root',type=pathlib.Path);a=p.parse_args()
 for path,data in compose(a.source_root).items():path.parent.mkdir(parents=True,exist_ok=True);path.write_text(data)
