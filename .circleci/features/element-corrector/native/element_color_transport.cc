// Copyright 2026 Sandium Authors. BSD-style license.
#include "brave/browser/sandium/element_color_transport.h"
#include "content/public/browser/render_frame_host.h"
#include "third_party/blink/public/common/associated_interfaces/associated_interface_provider.h"
#include "mojo/public/cpp/bindings/callback_helpers.h"
namespace sandium {
bool MojoElementColorTransport::SameDocument(content::RenderFrameHost& frame) const {
  return remote_.is_bound() && document_.AsRenderFrameHostIfValid()==&frame;
}
void MojoElementColorTransport::Start(content::RenderFrameHost& frame,const base::UnguessableToken& token) {
  remote_.reset();document_=frame.GetWeakDocumentPtr();
  frame.GetRemoteAssociatedInterfaces()->GetInterface(&remote_);
  remote_->StartColorPicker(token);
}
void MojoElementColorTransport::Preview(content::RenderFrameHost& frame,const base::UnguessableToken& token,
    uint64_t node,int property,uint32_t rgb) {
  if (SameDocument(frame)) remote_->PreviewColor(token,node,property,rgb);
}
void MojoElementColorTransport::Commit(content::RenderFrameHost& frame,const base::UnguessableToken& token,
    uint64_t node,int property,uint32_t rgb,base::OnceCallback<void(bool)> result) {
  if (!SameDocument(frame)) {std::move(result).Run(false);return;}
  remote_->CommitColor(token,node,property,rgb,
      mojo::WrapCallbackWithDefaultInvokeIfNotRun(std::move(result),false));
}
void MojoElementColorTransport::Cancel(content::RenderFrameHost& frame,const base::UnguessableToken& token) {
  if (SameDocument(frame)) remote_->CancelColorPicker(token);
}
void MojoElementColorTransport::Clear(content::RenderFrameHost& frame,const base::UnguessableToken& token) {
  if (SameDocument(frame)) remote_->ClearColorRules(token);
}

void MojoElementColorTransport::Restore(content::RenderFrameHost& frame,const base::UnguessableToken& token,base::ListValue rules) {
  remote_.reset();document_=frame.GetWeakDocumentPtr();
  frame.GetRemoteAssociatedInterfaces()->GetInterface(&remote_);
  remote_->RestoreColorRules(token,std::move(rules));
}

}
