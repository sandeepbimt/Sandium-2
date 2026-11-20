#if BUILDFLAG(IS_ANDROID)
namespace {

// Snapshot the issuing frame and its publisher before noopener disconnects
// the frame trees. Only this new tab can consume its pending check.
constexpr char kSandiumPendingPopupKey[] = "sandium-pending-popup";
// Share the deferral budget across the start and every redirect, but do not
// count normal network time. The early known-exchange guard is independent.
constexpr auto kSandiumPopupCheckBudget = base::Milliseconds(100);

struct SandiumPopupSource final : base::SupportsUserData::Data {
  SandiumPopupSource(GURL frame, GURL publisher)
      : frame(std::move(frame)), publisher(std::move(publisher)) {}
  const GURL frame;
  const GURL publisher;
  const base::TimeTicks opened = base::TimeTicks::Now();
};

bool ShouldCheckSandiumPopup(content::WebContents* contents,
                             const GURL& publisher,
                             const GURL& destination) {
  auto* profile = Profile::FromBrowserContext(contents->GetBrowserContext());
  auto* settings = HostContentSettingsMapFactory::GetForProfile(profile);
  return settings &&
         brave_shields::IsBraveShieldsEnabled(settings, publisher) &&
         brave_shields::IsBraveShieldsEnabled(settings, destination) &&
         settings->GetContentSetting(publisher, publisher,
                                     ContentSettingsType::POPUPS) !=
             CONTENT_SETTING_ALLOW &&
         brave_shields::ShouldBlockAdRedirect(*profile->GetPrefs(), publisher);
}

class SandiumPopupNavigationThrottle final
    : public content::NavigationThrottle {
 public:
  static void MaybeCreateAndAdd(content::NavigationThrottleRegistry& registry) {
    auto& handle = registry.GetNavigationHandle();
    if (!handle.IsInPrimaryMainFrame()) {
      return;
    }
    auto* contents = handle.GetWebContents();
    auto* source = static_cast<const SandiumPopupSource*>(
        contents->GetUserData(kSandiumPendingPopupKey));
    if (!source) {
      return;
    }
    // about:blank can precede the real first document. A browser-initiated
    // navigation (e.g. typing/bookmarking) always retires popup provenance.
    const bool eligible =
        handle.IsRendererInitiated() &&
        base::TimeTicks::Now() - source->opened <= base::Seconds(10);
    if (eligible && handle.GetURL().IsAboutBlank()) {
      return;
    }
    if (eligible && !handle.IsSameDocument() &&
        handle.GetURL().SchemeIsHTTPOrHTTPS()) {
      registry.AddThrottle(std::make_unique<SandiumPopupNavigationThrottle>(
          registry, source->frame, source->publisher));
    }
    contents->RemoveUserData(kSandiumPendingPopupKey);
  }

  SandiumPopupNavigationThrottle(content::NavigationThrottleRegistry& registry,
                                 const GURL& frame,
                                 const GURL& publisher)
      : NavigationThrottle(registry), frame_(frame), publisher_(publisher) {}

  ThrottleCheckResult WillStartRequest() override { return Check(); }
  ThrottleCheckResult WillRedirectRequest() override { return Check(); }
  const char* GetNameForLogging() override {
    return "SandiumPopupNavigationThrottle";
  }

 private:
  ThrottleCheckResult Check() {
    const auto& target = navigation_handle()->GetURL();
    auto* service = g_brave_browser_process->ad_block_service();
    if (!service || remaining_budget_ <= base::TimeDelta() ||
        !target.SchemeIsHTTPOrHTTPS() ||
        !ShouldCheckSandiumPopup(navigation_handle()->GetWebContents(),
                                 publisher_, target)) {
      return PROCEED;
    }
    check_started_ = base::TimeTicks::Now();
    check_timer_.Start(
        FROM_HERE, remaining_budget_,
        base::BindOnce(&SandiumPopupNavigationThrottle::OnChecked,
                       weak_factory_.GetWeakPtr(), false));
    service->AsyncCallAndReplyWithResult<bool>(
        base::BindOnce(
            [](GURL target, GURL source,
               brave_shields::AdBlockEngineWrapper* engine) {
              return engine->ShouldBlockSandiumPopup(target, source);
            },
            target, frame_),
        base::BindOnce(&SandiumPopupNavigationThrottle::OnChecked,
                       weak_factory_.GetWeakPtr()));
    return DEFER;
  }

  void OnChecked(bool blocked) {
    check_timer_.Stop();
    weak_factory_.InvalidateWeakPtrs();
    remaining_budget_ -= base::TimeTicks::Now() - check_started_;
    if (blocked &&
        ShouldCheckSandiumPopup(navigation_handle()->GetWebContents(),
                                publisher_, navigation_handle()->GetURL())) {
      CancelDeferredNavigation(CANCEL_AND_IGNORE);
      return;
    }
    Resume();
  }

  const GURL frame_;
  const GURL publisher_;
  base::TimeDelta remaining_budget_ = kSandiumPopupCheckBudget;
  base::TimeTicks check_started_;
  base::OneShotTimer check_timer_;
  base::WeakPtrFactory<SandiumPopupNavigationThrottle> weak_factory_{this};
};

}  // namespace

void BraveContentBrowserClient::OnSandiumScriptedPopupCreated(
    content::RenderFrameHost* opener,
    content::WebContents* new_contents) {
  GURL frame = opener->GetLastCommittedURL();
  if (!frame.SchemeIsHTTPOrHTTPS()) {
    frame = opener->GetLastCommittedOrigin().GetURL();
  }
  const GURL publisher = opener->GetOutermostMainFrame()->GetLastCommittedURL();
  if (frame.SchemeIsHTTPOrHTTPS() && publisher.SchemeIsHTTPOrHTTPS()) {
    new_contents->SetUserData(
        kSandiumPendingPopupKey,
        std::make_unique<SandiumPopupSource>(std::move(frame), publisher));
  }
}
#endif  // BUILDFLAG(IS_ANDROID)
