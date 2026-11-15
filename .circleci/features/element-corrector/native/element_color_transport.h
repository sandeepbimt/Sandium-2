// Copyright 2026 Sandium Authors. BSD-style license.
#ifndef BRAVE_BROWSER_SANDIUM_ELEMENT_COLOR_TRANSPORT_H_
#define BRAVE_BROWSER_SANDIUM_ELEMENT_COLOR_TRANSPORT_H_
#include "brave/browser/sandium/element_color_session.h"
#include "brave/components/cosmetic_filters/common/cosmetic_filters.mojom.h"
#include "mojo/public/cpp/bindings/associated_remote.h"
namespace sandium {
// Dedicated interface: does not reset the existing element-blocker Agent receiver.
class MojoElementColorTransport final : public ElementColorTransport {
 public:
  void Start(content::RenderFrameHost&,const base::UnguessableToken&) override;
  void Preview(content::RenderFrameHost&,const base::UnguessableToken&,uint64_t,int,uint32_t) override;
  void Commit(content::RenderFrameHost&,const base::UnguessableToken&,uint64_t,int,uint32_t,
              base::OnceCallback<void(bool)>) override;
  void Cancel(content::RenderFrameHost&,const base::UnguessableToken&) override;
  void Restore(content::RenderFrameHost&,const base::UnguessableToken&,base::ListValue) override;
  void Clear(content::RenderFrameHost&,const base::UnguessableToken&) override;
 private:
  bool SameDocument(content::RenderFrameHost&) const;
  content::WeakDocumentPtr document_;
  mojo::AssociatedRemote<cosmetic_filters::mojom::ElementColorAgent> remote_;
};
}
#endif
