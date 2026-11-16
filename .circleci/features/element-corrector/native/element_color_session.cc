// Copyright 2026 Sandium Authors. BSD-style license.
#include "brave/browser/sandium/element_color_session.h"
#include "brave/browser/sandium/element_color_rule_store.h"
#include "brave/browser/sandium/element_color_transport.h"
#include "brave/browser/android/cosmetic_filters/sandium_element_colors_utils.h"
#include "base/functional/bind.h"
#include "base/location.h"
#include "base/time/time.h"
#include "chrome/browser/profiles/profile.h"
#include "content/public/browser/navigation_handle.h"
#include "content/public/browser/render_frame_host.h"
#include "content/public/browser/web_contents.h"
namespace sandium {
WEB_CONTENTS_USER_DATA_KEY_IMPL(ElementColorSession);
ElementColorSession& ElementColorSession::GetOrCreate(content::WebContents* contents) {
  CreateForWebContents(contents);return *FromWebContents(contents);
}
ElementColorSession::ElementColorSession(content::WebContents* contents)
    : ElementColorSession(contents,std::make_unique<MojoElementColorTransport>()) {}
namespace {
bool ValidVisitRule(const base::DictValue& rule) {
  auto check=rule.Clone();
  const auto* id=check.FindString("id");
  if (id && id->empty() && !check.Find("locator")) check.Set("id","visit-only");
  return ElementColorRuleStore::ValidRule(check);
}
}

ElementColorSession::ElementColorSession(content::WebContents* contents,
    std::unique_ptr<ElementColorTransport> transport)
    : WebContentsObserver(contents), WebContentsUserData<ElementColorSession>(*contents), transport_(std::move(transport)) {}
ElementColorSession::~ElementColorSession() {
  shutting_down_=true;lifetime_factory_.InvalidateWeakPtrs();Cancel();
}
content::RenderFrameHost* ElementColorSession::Current() const {
  auto* frame = document_.AsRenderFrameHostIfValid();
  if (shutting_down_ || !session_ || !web_contents() || !frame || !frame->IsActive() ||
      !frame->IsInPrimaryMainFrame() || frame != web_contents()->GetPrimaryMainFrame() ||
      web_contents()->GetVisibility() != content::Visibility::VISIBLE ||
      frame->GetLastCommittedOrigin() != origin_) return nullptr;
  return frame;
}
bool ElementColorSession::Begin(int64_t request_id) {
  if(shutting_down_)return false;
  auto alive=lifetime_factory_.GetWeakPtr();
  const uint64_t generation=++begin_generation_;
  Cancel();
  if(!alive || begin_generation_!=generation)return false;
  if (request_id<=0 || !transport_ || !web_contents() ||
      web_contents()->GetVisibility() != content::Visibility::VISIBLE) return false;
  auto* frame = web_contents()->GetPrimaryMainFrame();
  if (!frame || !frame->IsActive() || !frame->IsInPrimaryMainFrame()) return false;
  auto origin = frame->GetLastCommittedOrigin();
  if (origin.opaque() || !origin.GetURL().SchemeIsHTTPOrHTTPS()) return false;
  origin_ = origin;
  document_ = frame->GetWeakDocumentPtr();
  session_ = base::UnguessableToken::Create();
  request_id_=request_id;
  transport_->Start(*frame,*session_);
  return true;
}
bool ElementColorSession::OfferSelection(content::RenderFrameHost& sender,
    const base::UnguessableToken& token, uint64_t node, const base::DictValue& descriptor) {
  auto* frame = Current();
  if (!frame || request_id_<=0 || frame != &sender || *session_ != token || !node || saving_ || (descriptor.size()!=4 && descriptor.size()!=5))
    return false;
  auto check = descriptor.Clone(); check.Set("property",0); check.Set("rgb",0);
  if (!ValidVisitRule(check)) return false;
  descriptor_ = descriptor.Clone(); selected_node_ = node;
  NotifyElementColorSelection(web_contents(),request_id_);
  return true;
}
bool ElementColorSession::Preview(int property, uint32_t rgb) {
  auto* frame = Current();
  if (!frame || !descriptor_ || !selected_node_ || saving_) return false;
  auto check = descriptor_->Clone(); check.Set("property",property); check.Set("rgb",static_cast<int>(rgb));
  if (!ValidVisitRule(check) || rgb > 0xffffff) return false;
  transport_->Preview(*frame,*session_,selected_node_,property,rgb);
  return true;
}
void ElementColorSession::Save(int property, uint32_t rgb,
    base::OnceCallback<void(SaveResult)> result) {
  auto* frame = Current();
  if (!frame || !descriptor_ || !selected_node_ || saving_ || rgb > 0xffffff) {
    std::move(result).Run(SaveResult::kRejected); return;
  }
  auto rule=descriptor_->Clone();rule.Set("property",property);rule.Set("rgb",static_cast<int>(rgb));
  if (!ValidVisitRule(rule)) {
    std::move(result).Run(SaveResult::kRejected);return;
  }
  saving_=true;
  pending_result_=std::move(result);
  save_timeout_.Start(FROM_HERE,base::Seconds(5),
      base::BindOnce(&ElementColorSession::Cancel,weak_factory_.GetWeakPtr()));
  transport_->Commit(*frame,*session_,selected_node_,property,rgb,
      base::BindOnce(&ElementColorSession::OnCommitted,weak_factory_.GetWeakPtr(),
                     *session_,std::move(rule)));
}
void ElementColorSession::OnCommitted(base::UnguessableToken token, base::DictValue rule,
    bool applied) {
  // Cancel invalidates weak callbacks; same-RFH new document is rejected by WeakDocumentPtr.
  auto* frame=Current();
  if (!frame || *session_!=token || !saving_) { Cancel(); return; }
  saving_=false;
  save_timeout_.Stop();
  auto result=std::move(pending_result_);
  if (!applied) {std::move(result).Run(SaveResult::kRejected);return;}
  auto* profile=Profile::FromBrowserContext(frame->GetBrowserContext());
  bool saved=ElementColorRuleStore::ForProfile(*profile).Save(origin_,rule);
  std::move(result).Run(saved ? SaveResult::kSaved : SaveResult::kAppliedThisVisitOnly);
}
void ElementColorSession::Cancel() {
  auto* frame=document_.AsRenderFrameHostIfValid();
  auto token=session_;
  auto contents=web_contents() ? web_contents()->GetWeakPtr() : base::WeakPtr<content::WebContents>();
  auto result=std::move(pending_result_);
  const int64_t ended_id=request_id_;
  request_id_=0;
  save_timeout_.Stop();
  // Invalidate acknowledgments BEFORE transport cancellation, which may reenter.
  weak_factory_.InvalidateWeakPtrs();
  session_.reset();document_=content::WeakDocumentPtr();descriptor_.reset();
  selected_node_=0;saving_=false;origin_=url::Origin();
  if (frame && token && transport_) transport_->Cancel(*frame,*token);
  if (result) std::move(result).Run(SaveResult::kRejected);
  if (ended_id && contents) NotifyElementColorSessionEnded(contents.get(),ended_id);
}
void ElementColorSession::ResetSite() {
  auto* frame=Current();
  if (!frame) return;
  auto* profile=Profile::FromBrowserContext(frame->GetBrowserContext());
  ElementColorRuleStore::ForProfile(*profile).Reset(origin_);
  transport_->Clear(*frame,*session_);
  Cancel();
}
void ElementColorSession::DOMContentLoaded(content::RenderFrameHost* frame) {
  if (shutting_down_ || session_ || !frame || !frame->IsInPrimaryMainFrame() || !frame->IsActive() ||
      frame!=web_contents()->GetPrimaryMainFrame()) return;
  auto origin=frame->GetLastCommittedOrigin();
  if (origin.opaque() || !origin.GetURL().SchemeIsHTTPOrHTTPS()) return;
  auto* profile=Profile::FromBrowserContext(frame->GetBrowserContext());
  auto rules=ElementColorRuleStore::ForProfile(*profile).Read(origin);
  if(rules.empty())return;
  origin_=origin;document_=frame->GetWeakDocumentPtr();session_=base::UnguessableToken::Create();
  transport_->Restore(*frame,*session_,std::move(rules));
}
void ElementColorSession::DidFinishNavigation(content::NavigationHandle* handle) {
  if (handle->HasCommitted() && handle->IsInPrimaryMainFrame()) {
    auto alive=lifetime_factory_.GetWeakPtr();
    const uint64_t generation=begin_generation_;
    const bool restored=handle->IsServedFromBackForwardCache() || handle->IsPrerenderedPageActivation();
    Cancel();
    if(!alive || begin_generation_!=generation)return;
    if(!shutting_down_ && restored) DOMContentLoaded(web_contents()->GetPrimaryMainFrame());
  }
}
void ElementColorSession::OnVisibilityChanged(content::Visibility visibility) {
  if (visibility!=content::Visibility::VISIBLE) Cancel();
}
void ElementColorSession::WebContentsDestroyed() {
  shutting_down_=true;lifetime_factory_.InvalidateWeakPtrs();Cancel();
}
}  // namespace sandium
