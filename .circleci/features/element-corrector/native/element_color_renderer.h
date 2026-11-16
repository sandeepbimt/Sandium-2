// Copyright 2026 Sandium Authors. BSD-style license.
#ifndef BRAVE_COMPONENTS_COSMETIC_FILTERS_RENDERER_ELEMENT_COLOR_RENDERER_H_
#define BRAVE_COMPONENTS_COSMETIC_FILTERS_RENDERER_ELEMENT_COLOR_RENDERER_H_
#include <map>
#include <optional>
#include "base/memory/weak_ptr.h"
#include "brave/components/cosmetic_filters/common/cosmetic_filters.mojom.h"
#include "content/public/renderer/render_frame_observer.h"
#include "mojo/public/cpp/bindings/associated_receiver.h"
#include "mojo/public/cpp/bindings/associated_remote.h"
#include "third_party/blink/public/web/web_document.h"
#include "third_party/blink/public/web/web_element.h"
#include "v8/include/v8.h"
namespace cosmetic_filters {
class ElementColorRenderer final : public content::RenderFrameObserver,
                                  public mojom::ElementColorAgent {
 public:
  ElementColorRenderer(content::RenderFrame*,int isolated_world);
  ~ElementColorRenderer() override;
  void BindWorker(v8::Isolate*,v8::Local<v8::Object>);
  void ReadyToCommitNavigation(blink::WebDocumentLoader*) override;
  void OnDestruct() override;
 private:
  void Bind(mojo::PendingAssociatedReceiver<mojom::ElementColorAgent>);
  void RestoreColorRules(const base::UnguessableToken&,base::ListValue) override;
  bool RestoreNode(v8::Isolate*,v8::Local<v8::Value>,int);
  void StartColorPicker(const base::UnguessableToken&) override;
  void PreviewColor(const base::UnguessableToken&,uint64_t,int32_t,uint32_t) override;
  void CommitColor(const base::UnguessableToken&,uint64_t,int32_t,uint32_t,CommitColorCallback) override;
  void ClearColorRules(const base::UnguessableToken&) override;
  void CancelColorPicker(const base::UnguessableToken&) override;
  void Select(v8::Isolate*,v8::Local<v8::Value>,const std::string&);
  bool DescriptorMatches(uint64_t,const blink::WebElement&) const;
  bool Current(const base::UnguessableToken&) const;
  void Execute(const std::string&);
  void Reset(bool clear_saved);
  const int world_;
  uint64_t next_=0;
  base::ListValue remembered_;
  std::optional<base::UnguessableToken> session_;
  blink::WebDocument document_;
  std::map<uint64_t,blink::WebElement> nodes_;
  std::map<uint64_t,base::DictValue> descriptors_;
  mojo::AssociatedReceiver<mojom::ElementColorAgent> receiver_{this};
  mojo::AssociatedRemote<mojom::CosmeticFiltersHandler> browser_;
  base::WeakPtrFactory<ElementColorRenderer> weak_factory_{this};
};
}
#endif
