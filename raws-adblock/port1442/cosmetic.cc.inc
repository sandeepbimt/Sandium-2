#if BUILDFLAG(IS_ANDROID)
namespace {
// Retain native browser-side document identity across the asynchronous query.
// Only push URL-specific CSS for the document that actually committed. Do not
// create an observer for every network request or issue renderer JS calls.
class RawSCosmeticObserver final : public content::WebContentsObserver,
                                   public content::WebContentsUserData<RawSCosmeticObserver> {
 public:
  ~RawSCosmeticObserver() override = default;
  void DidFinishNavigation(content::NavigationHandle* handle) override {
    if (!handle->HasCommitted() || handle->IsErrorPage() || handle->IsSameDocument() ||
        !handle->GetURL().SchemeIsHTTPOrHTTPS()) return;
    auto* frame = handle->GetRenderFrameHost();
    if (!frame || !frame->IsActive() ||
        frame->GetLastCommittedOrigin().opaque()) {
      return;
    }
    sandium::adblock_native::QueryHideStyles(
        handle->GetURL(),
        base::BindOnce(
            [](content::WeakDocumentPtr document, GURL url, std::string css) {
              auto* target = document.AsRenderFrameHostIfValid();
              if (!target || !target->IsActive() ||
                  !target->IsRenderFrameLive() ||
                  target->GetLastCommittedURL() != url || css.empty()) {
                return;
              }
              mojo::AssociatedRemote<chrome::mojom::ChromeRenderFrame> remote;
              target->GetRemoteAssociatedInterfaces()->GetInterface(&remote);
              remote->ApplyRawSHideStyles(url, css);
            },
            frame->GetWeakDocumentPtr(), handle->GetURL()));
  }
 private:
  explicit RawSCosmeticObserver(content::WebContents* contents)
      : content::WebContentsObserver(contents),content::WebContentsUserData<RawSCosmeticObserver>(*contents) {}
  friend class content::WebContentsUserData<RawSCosmeticObserver>;
  WEB_CONTENTS_USER_DATA_KEY_DECL();
};
WEB_CONTENTS_USER_DATA_KEY_IMPL(RawSCosmeticObserver);
}  // namespace
#endif
