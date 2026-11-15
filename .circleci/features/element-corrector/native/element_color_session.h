// Copyright 2026 Sandium Authors. BSD-style license.
#ifndef BRAVE_BROWSER_SANDIUM_ELEMENT_COLOR_SESSION_H_
#define BRAVE_BROWSER_SANDIUM_ELEMENT_COLOR_SESSION_H_
#include <memory>
#include <optional>
#include "base/functional/callback.h"
#include "base/memory/weak_ptr.h"
#include "base/unguessable_token.h"
#include "base/values.h"
#include "base/timer/timer.h"
#include "content/public/browser/weak_document_ptr.h"
#include "content/public/browser/web_contents_observer.h"
#include "content/public/browser/web_contents_user_data.h"
#include "url/origin.h"
namespace content { class RenderFrameHost; }
namespace sandium {
// Implementation must use a document-scoped Mojo receiver. No page JS receives it.
class ElementColorTransport {
 public:
  virtual ~ElementColorTransport() = default;
  virtual void Start(content::RenderFrameHost&, const base::UnguessableToken&) = 0;
  virtual void Preview(content::RenderFrameHost&, const base::UnguessableToken&,
                       uint64_t node, int property, uint32_t rgb) = 0;
  virtual void Commit(content::RenderFrameHost&, const base::UnguessableToken&,
                      uint64_t node, int property, uint32_t rgb,
                      base::OnceCallback<void(bool)> acknowledged) = 0;
  virtual void Cancel(content::RenderFrameHost&, const base::UnguessableToken&) = 0;
  virtual void Restore(content::RenderFrameHost&,const base::UnguessableToken&,base::ListValue) = 0;
  virtual void Clear(content::RenderFrameHost&, const base::UnguessableToken&) = 0;
};
class ElementColorSession final : public content::WebContentsObserver,
    public content::WebContentsUserData<ElementColorSession> {
 public:
  enum class SaveResult { kSaved, kAppliedThisVisitOnly, kRejected };
  ElementColorSession(content::WebContents*, std::unique_ptr<ElementColorTransport>);
  ~ElementColorSession() override;
  // Begin, Preview and Save must be wired only to browser-owned Android controls.
  static ElementColorSession& GetOrCreate(content::WebContents*);
  bool Begin(int64_t request_id);
  int64_t request_id() const { return request_id_; }
  void ResetSite();
  bool OfferSelection(content::RenderFrameHost&, const base::UnguessableToken&,
                      uint64_t node, const base::DictValue& descriptor);
  bool Preview(int property, uint32_t rgb);
  void Save(int property, uint32_t rgb, base::OnceCallback<void(SaveResult)>);
  void Cancel();
  void DOMContentLoaded(content::RenderFrameHost*) override;
  void DidFinishNavigation(content::NavigationHandle*) override;
  void OnVisibilityChanged(content::Visibility) override;
  void WebContentsDestroyed() override;
 private:
  explicit ElementColorSession(content::WebContents*);
  friend class content::WebContentsUserData<ElementColorSession>;
  WEB_CONTENTS_USER_DATA_KEY_DECL();
  content::RenderFrameHost* Current() const;
  void OnCommitted(base::UnguessableToken, base::DictValue, bool);
  std::unique_ptr<ElementColorTransport> transport_;
  content::WeakDocumentPtr document_;
  std::optional<base::UnguessableToken> session_;
  url::Origin origin_;
  uint64_t selected_node_ = 0;
  std::optional<base::DictValue> descriptor_;
  bool saving_ = false;
  bool shutting_down_ = false;
  int64_t request_id_ = 0;
  uint64_t begin_generation_ = 0;
  base::OneShotTimer save_timeout_;
  base::OnceCallback<void(SaveResult)> pending_result_;
  base::WeakPtrFactory<ElementColorSession> weak_factory_{this};
  base::WeakPtrFactory<ElementColorSession> lifetime_factory_{this};
};
}  // namespace sandium
#endif
