#if BUILDFLAG(IS_ANDROID)
namespace {
// Do not classify an iframe as an ad just because it is empty. A positive
// native subdocument verdict is required before Chromium collapses its owner.
class RawSSubframeFilter final : public content::NavigationThrottle {
 public:
  explicit RawSSubframeFilter(content::NavigationThrottleRegistry& r) : NavigationThrottle(r) {}
  ThrottleCheckResult WillStartRequest() override { return Check(); }
  ThrottleCheckResult WillRedirectRequest() override { return Check(); }
  const char* GetNameForLogging() override { return "RawSSubframeFilter"; }
 private:
  ThrottleCheckResult Check() {
    auto* h=navigation_handle();auto* parent=h->GetParentFrame();
    if (!parent || h->IsSameDocument() || h->IsPost() || !h->IsRendererInitiated() ||
        !h->GetURL().SchemeIsHTTPOrHTTPS() || budget_<=base::TimeDelta()) return PROCEED;
    const auto& initiator=h->GetInitiatorOrigin();
    if (!initiator || initiator->opaque() || *initiator!=parent->GetLastCommittedOrigin()) return PROCEED;
    if (!sandium::adblock_native::CheckSubframe(h->GetURL(),*initiator,
          base::BindOnce(&RawSSubframeFilter::Finish,weak_.GetWeakPtr()))) return PROCEED;
    start_=base::TimeTicks::Now();timer_.Start(FROM_HERE,budget_,base::BindOnce(&RawSSubframeFilter::Finish,weak_.GetWeakPtr(),false));
    return DEFER;
  }
  void Finish(bool block){timer_.Stop();weak_.InvalidateWeakPtrs();budget_-=base::TimeTicks::Now()-start_;
    if(block) CancelDeferredNavigation(BLOCK_REQUEST_AND_COLLAPSE); else Resume();}
  base::TimeDelta budget_=base::Milliseconds(50);
  base::TimeTicks start_;base::OneShotTimer timer_;base::WeakPtrFactory<RawSSubframeFilter> weak_{this};
};
}
#endif
