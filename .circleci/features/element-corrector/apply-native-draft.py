#!/usr/bin/env python3
"""Offline source-composition only. NOT called by pipeline. No browser entry point."""
import argparse, pathlib
ROOT=pathlib.Path(__file__).resolve().parent
INCLUDE='#include "third_party/blink/renderer/core/dom/sandium_element_colors.h"\n'
def once(s,old,new):
    if new in s:return s
    if s.count(old)!=1:raise ValueError('Pinned anchor mismatch: '+old[:80])
    return s.replace(old,new,1)
def compose(root):
    edits={}
    def change(path,fn):
        target=root/path;edits[target]=fn(target.read_text())
    dom='third_party/blink/renderer/core/dom/'
    change(dom+'element.cc',lambda s:once(once(s,'#include "third_party/blink/renderer/core/dom/element.h"\n', '#include "third_party/blink/renderer/core/dom/element.h"\n'+INCLUDE),
       'void Element::RemovedFrom(ContainerNode& insertion_point) {',
       'void Element::RemovedFrom(ContainerNode& insertion_point) {\n  if (auto* colors = SandiumElementColors::GetIfExists(GetDocument()))\n    colors->Remove(*this);'))
    style='third_party/blink/renderer/core/css/resolver/style_adjuster.cc'
    def adjust(s):
      s=once(s,'#include "third_party/blink/renderer/core/css/resolver/style_adjuster.h"\n','#include "third_party/blink/renderer/core/css/resolver/style_adjuster.h"\n'+INCLUDE)
      anchor='  ApplySandiumPaintPolicy(builder, element, element_or_pseudo_element, parent_style);'
      addition=anchor+'\n  // Exact manual choices take precedence over automatic palette/stock darkening.\n  if (element_or_pseudo_element == &element) {\n    if (auto* colors = SandiumElementColors::GetIfExists(element.GetDocument()))\n      colors->Apply(element, builder);\n  }'
      return once(s,anchor,addition)
    change(style,adjust)
    change('third_party/blink/renderer/core/BUILD.gn',lambda s:once(s,
      '  sources += rebase_path(blink_core_sources_dom, "", "dom")',
      '  sources += rebase_path(blink_core_sources_dom, "", "dom")\n  sources += [ "dom/sandium_element_colors.cc", "dom/sandium_element_colors.h" ]'))
    header='third_party/blink/public/web/web_element.h'
    decl='  static WebElement FromV8Value(v8::Isolate*, v8::Local<v8::Value>);'
    change(header,lambda s:once(s,decl,decl+'\n\n  // Sandium internal browser-owned session only; not exposed to page JavaScript.\n  bool SandiumPreviewColor(int property, unsigned rgb);\n  bool SandiumCommitColor(int property, unsigned rgb);\n  void SandiumCancelColorPreview();\n  void SandiumClearColors();'))
    def public(s):
      s=once(s,'#include "third_party/blink/public/web/web_element.h"\n','#include "third_party/blink/public/web/web_element.h"\n'+INCLUDE)
      methods='''bool WebElement::SandiumPreviewColor(int property, unsigned rgb) {
  if (IsNull()) return false;
  Element* element = Unwrap<Element>();
  return SandiumElementColors::From(element->GetDocument()).Preview(*element, property, rgb);
}
bool WebElement::SandiumCommitColor(int property, unsigned rgb) {
  if (IsNull()) return false;
  Element* element = Unwrap<Element>();
  return SandiumElementColors::From(element->GetDocument()).Commit(*element, property, rgb);
}
void WebElement::SandiumCancelColorPreview() {
  if (IsNull()) return;
  if (auto* colors = SandiumElementColors::GetIfExists(Unwrap<Element>()->GetDocument()))
    colors->CancelPreview();
}
void WebElement::SandiumClearColors() {
  if (IsNull()) return;
  if (auto* colors = SandiumElementColors::GetIfExists(Unwrap<Element>()->GetDocument()))
    colors->Clear();
}

}  // namespace blink'''
      return once(s,'}  // namespace blink',methods)
    change('third_party/blink/renderer/core/exported/web_element.cc',public)
    for name in ['sandium_element_colors.h','sandium_element_colors.cc']:
      edits[root/dom/name]=(ROOT/'native'/name).read_text()
    return edits
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source_root',type=pathlib.Path);a=p.parse_args()
    for path,data in compose(a.source_root).items():path.write_text(data)
