// Copyright 2026 Sandium Authors. BSD-style license.
#include "brave/components/cosmetic_filters/renderer/element_color_renderer.h"
#include "brave/components/cosmetic_filters/renderer/element_color_picker_script.h"
#include "base/functional/bind.h"
#include "base/json/json_reader.h"
#include "base/json/json_writer.h"
#include "base/strings/string_util.h"
#include <vector>
#include "content/public/renderer/render_frame.h"
#include "gin/function_template.h"
#include "gin/converter.h"
#include "third_party/blink/public/common/associated_interfaces/associated_interface_registry.h"
#include "third_party/blink/public/common/associated_interfaces/associated_interface_provider.h"
#include "third_party/blink/public/platform/web_string.h"
#include "third_party/blink/public/web/web_local_frame.h"
#include "third_party/blink/public/web/web_script_source.h"
namespace cosmetic_filters {
ElementColorRenderer::ElementColorRenderer(content::RenderFrame* frame,int world)
    : RenderFrameObserver(frame),world_(world) {
  frame->GetAssociatedInterfaceRegistry()->AddInterface<mojom::ElementColorAgent>(
      base::BindRepeating(&ElementColorRenderer::Bind,weak_factory_.GetWeakPtr()));
}
ElementColorRenderer::~ElementColorRenderer() = default;
void ElementColorRenderer::Bind(mojo::PendingAssociatedReceiver<mojom::ElementColorAgent> receiver) {
  receiver_.reset();receiver_.Bind(std::move(receiver));
}
void ElementColorRenderer::BindWorker(v8::Isolate* isolate,v8::Local<v8::Object> object) {
  object->Set(isolate->GetCurrentContext(),gin::StringToSymbol(isolate,"sandiumRestore"),
      gin::CreateFunctionTemplate(isolate,base::BindRepeating(&ElementColorRenderer::RestoreNode,
          base::Unretained(this),isolate))->GetFunction(isolate->GetCurrentContext()).ToLocalChecked()).Check();
  object->Set(isolate->GetCurrentContext(),gin::StringToSymbol(isolate,"sandiumSelect"),
      gin::CreateFunctionTemplate(isolate,base::BindRepeating(&ElementColorRenderer::Select,
          base::Unretained(this),isolate))->GetFunction(isolate->GetCurrentContext()).ToLocalChecked()).Check();
}
bool ElementColorRenderer::Current(const base::UnguessableToken& token) const {
  auto* frame=render_frame() ? render_frame()->GetWebFrame() : nullptr;
  return frame && !frame->Parent() && !frame->IsProvisional() && session_ &&
      *session_==token && frame->GetDocument()==document_;
}
void ElementColorRenderer::Execute(const std::string& script) {
  auto* frame=render_frame()->GetWebFrame();
  frame->ExecuteScriptInIsolatedWorld(world_,blink::WebScriptSource(blink::WebString::FromUtf8(script)),
      blink::BackForwardCacheAware::kAllow);
}
void ElementColorRenderer::StartColorPicker(const base::UnguessableToken& token) {
  Reset(false);
  auto* frame=render_frame()->GetWebFrame();
  if (frame->Parent() || frame->IsProvisional()) return;
  document_=frame->GetDocument();session_=token;
  if (!browser_.is_bound()) render_frame()->GetRemoteAssociatedInterfaces()->GetInterface(&browser_);
  Execute(kSandiumElementPickerScript);
}
void ElementColorRenderer::RestoreColorRules(const base::UnguessableToken& token,base::ListValue rules) {
  Reset(false);
  auto* frame=render_frame()->GetWebFrame();
  if(frame->Parent() || frame->IsProvisional() || rules.size()>32)return;
  document_=frame->GetDocument();session_=token;remembered_=std::move(rules);
  auto json=base::WriteJson(remembered_);
  if(!json || json->size()>262144)return;
  Execute(std::string(kSandiumElementCoreScript)+";const rules="+*json+
      ";rules.forEach((rule,index)=>{const node=matchRemembered(rule,document);if(node)cf_worker.sandiumRestore(node,index);});})();");
  remembered_.clear();
}
void ElementColorRenderer::RestoreNode(v8::Isolate* isolate,v8::Local<v8::Value> value,int index) {
  if(!session_ || !Current(*session_) || index<0 || static_cast<size_t>(index)>=remembered_.size() || nodes_.size()>=64)return;
  const auto* rule=remembered_[index].GetIfDict();if(!rule)return;
  auto property=rule->FindInt("property"),rgb=rule->FindInt("rgb");
  auto node=blink::WebElement::FromV8Value(isolate,value);
  if(!property || !rgb || *rgb<0 || node.IsNull() || !node.IsConnected() || node.GetDocument()!=document_)return;
  if(node.SandiumCommitColor(*property,static_cast<uint32_t>(*rgb)))nodes_.emplace(++next_,node);
}
void ElementColorRenderer::Select(v8::Isolate* isolate,v8::Local<v8::Value> value,const std::string& descriptor) {
  if (!session_ || !Current(*session_) || nodes_.size()>=64 || descriptor.size()>8192) return;
  auto node=blink::WebElement::FromV8Value(isolate,value);
  if (node.IsNull() || !node.IsConnected() || node.GetDocument()!=document_) return;
  auto parsed=base::JSONReader::ReadDict(descriptor);
  if (!parsed) return;
  const uint64_t id=++next_;nodes_.emplace(id,node);descriptors_.emplace(id,parsed->Clone());
  browser_->OfferElementColorSelection(*session_,id,std::move(*parsed),base::BindOnce([](bool){}));
}
void ElementColorRenderer::PreviewColor(const base::UnguessableToken& token,uint64_t id,int32_t property,uint32_t rgb) {
  if (!Current(token)) return;
  auto found=nodes_.find(id);
  if (found!=nodes_.end() && found->second.IsConnected() && found->second.GetDocument()==document_)
    found->second.SandiumPreviewColor(property,rgb);
}
bool ElementColorRenderer::DescriptorMatches(uint64_t id,const blink::WebElement& node) const {
  auto found=descriptors_.find(id);if(found==descriptors_.end())return false;
  const auto& expected=found->second;
  const auto* tag=expected.FindString("tag");const auto* key=expected.FindString("id");
  const auto* role=expected.FindString("role");const auto* ancestors=expected.FindList("ancestors");
  if(!tag || !key || !role || !ancestors || *tag!=base::ToLowerASCII(node.TagName().Utf8()) ||
      (!key->empty() && *key!=node.GetAttribute(blink::WebString::FromUtf8("id")).Utf8()) ||
      *role!=node.GetAttribute(blink::WebString::FromUtf8("role")).Utf8())return false;
  std::vector<base::DictValue> parents;
  for(auto parent=node.ParentNode().DynamicTo<blink::WebElement>();!parent.IsNull();
      parent=parent.ParentNode().DynamicTo<blink::WebElement>()) {
    auto name=base::ToLowerASCII(parent.TagName().Utf8());if(name=="html")break;
    if(parents.size()>=24)return false;
    base::DictValue value;value.Set("tag",name);value.Set("id",parent.GetAttribute(blink::WebString::FromUtf8("id")).Utf8());
    parents.push_back(std::move(value));
  }
  base::ListValue actual;for(auto it=parents.rbegin();it!=parents.rend();++it)actual.Append(it->Clone());
  return actual==*ancestors;
}
void ElementColorRenderer::CommitColor(const base::UnguessableToken& token,uint64_t id,int32_t property,uint32_t rgb,
    CommitColorCallback result) {
  auto found=nodes_.find(id);
  bool success=Current(token) && found!=nodes_.end() && found->second.IsConnected() &&
      found->second.GetDocument()==document_ && DescriptorMatches(id,found->second) && found->second.SandiumCommitColor(property,rgb);
  std::move(result).Run(success);
}
void ElementColorRenderer::ClearColorRules(const base::UnguessableToken& token) {
  if(Current(token)) Reset(true);
}
void ElementColorRenderer::CancelColorPicker(const base::UnguessableToken& token) {
  if (Current(token)) Reset(false);
}
void ElementColorRenderer::Reset(bool clear_saved) {
  if (session_ && Current(*session_)) Execute("globalThis.__sandiumCancelPicker?.();");
  // Cleanup binds to the captured Document, never an adopted selected node.
  auto root=document_.IsNull() ? blink::WebElement() : document_.DocumentElement();
  if(!root.IsNull()) {
    if(clear_saved)root.SandiumClearColors();
    else root.SandiumCancelColorPreview();
  }
  nodes_.clear();descriptors_.clear();remembered_.clear();session_.reset();document_=blink::WebDocument();browser_.reset();
}
void ElementColorRenderer::ReadyToCommitNavigation(blink::WebDocumentLoader*) {Reset(true);}
void ElementColorRenderer::OnDestruct() {Reset(true);}
}
