"""Byte-anchored #1514 transforms for a browser-authorized pre-parser player hook."""
from pathlib import Path

BROWSER = 'chrome/browser/raws/raws_site_ads_policy.h'
WIRE = 'chrome/common/chrome_render_frame.mojom'
HEADER = 'chrome/renderer/chrome_render_frame_observer.h'
RENDERER = 'chrome/renderer/chrome_render_frame_observer.cc'
CHROME_CC = 'chrome/browser/chrome_content_browser_client.cc'
CHROME_H = 'chrome/browser/chrome_content_browser_client.h'
CONTENT_CC = 'content/public/browser/content_browser_client.cc'
CONTENT_H = 'content/public/browser/content_browser_client.h'
NAV = 'content/browser/renderer_host/navigation_request.cc'
NAV_CONTROLLER = 'content/browser/renderer_host/navigation_controller_impl.cc'
NAV_ENTRY = 'content/browser/renderer_host/navigation_entry_impl.cc'
NAV_MOJOM = 'third_party/blink/public/mojom/navigation/navigation_params.mojom'
RENDER_FRAME = 'content/renderer/render_frame_impl.cc'
WEB_PARAMS = 'third_party/blink/public/web/web_navigation_params.h'
PUBLIC_LOADER = 'third_party/blink/public/web/web_document_loader.h'
LOADER_H = 'third_party/blink/renderer/core/loader/document_loader.h'
LOADER_CC = 'third_party/blink/renderer/core/loader/document_loader.cc'
OWNERS = {
    BROWSER: '49b2cb04a2d6e381666153ae9fffaed5ef79d9c3e0726cf33426580d6a3d1271',
    WIRE: 'e0dba842888e641ec8f1de710378f158770da67c21916a5a7f76b0b2937e3f39',
    HEADER: 'bd1fafdca493cbd0c73689f075a89b3c0693aa5b8dee5fbd13a1ded814efcbf9',
    RENDERER: '266b7b0069b04f7deca6fe87f25d50c72e1bd6807e05d825a7c9f729d96af9ac',
    CHROME_CC: 'deb0a7a102623f9994c7335af401c16102b31028845d1b82c380ea18d8b8668f',
    CHROME_H: '231f705d380e4475f590b8a05488ae5f2e11d25b7e54d9fb34511ac61d1ec378',
    CONTENT_CC: 'f5e1f098a700be82880f7cda6dc90c82b56b756e854076180098e64233f2560e',
    CONTENT_H: '461262a9e7c13ac41ec7d75bc3c68d46657a59b9263b076087f3289320c1f0ce',
    NAV: '1c61a0de27bc7c895fc270e71f929fe97ac15e22069d1702c53e2ccef918f09b',
    NAV_CONTROLLER: '1dcc898d6ecc3b6416af7b1a401ab83accba022ec538eb871727074f20a0e965',
    NAV_ENTRY: 'b93197da9227a061ff0adcc7202919ddd29c3c46125f25dc72c69798a8459d56',
    NAV_MOJOM: 'e6d3af2da99b4afc6b922ee39f1a71b8ecbf4192fb28f02d05ffc05ad04306fc',
    RENDER_FRAME: 'a0b5f6d57005b8f00143a56c6437985b543419626150f0ddd3ded8d6068c7cb0',
    WEB_PARAMS: 'f708ddded56749c19f95586cb38c48776d7c2c21eab484e9149617334c24a9c6',
    PUBLIC_LOADER: '2ace839782426eb01e0219fa367fe1469bd7f04a16c28d140ad02fe99f4f890c',
    LOADER_H: '357782059e92bf7cefc3843a9fa3357ee20828da26050362c02944302bdeb251',
    LOADER_CC: '143d68a3e33a0742001b497885a372c680e5fdcde48b03a42ffdd03a905e6b00',
}
UPSTREAM = {
    PUBLIC_LOADER: 'b6da61a76551f1de95b8cfb0a1167b14040f3dd1',
    LOADER_H: 'eec882554e19f51e5316d7f243ea104426254717',
    LOADER_CC: '84f8dd186a76fa20301287d6e38062b7ded6c30b',
}
NEW_TRACKED = {path: OWNERS[path] for path in UPSTREAM}
USES_COMMIT_POLICY = True


def once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise ValueError(f'missing or ambiguous anchor: {old[:100]!r}')
    return text.replace(old, new, 1)


def transform(path: str, src: bytes) -> bytes:
    text = src.decode('utf-8')
    if path == NAV:
        a = '          /*raws_page_text_policy=*/100);'
        if text.count(a) != 2:
            raise ValueError('expected exactly two positional commit constructors')
        text = text.replace(a, '''          /*raws_page_text_policy=*/100,
          /*raws_mobile_player_filtering=*/false);''')
        a = '  auto common_params = common_params_->Clone();\n  auto commit_params = commit_params_.Clone();\n  auto response_head = response_head_.Clone();'
        text = once(text, a, '''  // Compute from the final URL and the real new document security origin,
  // not from an initiator or previous page. The error commit retains false.
  commit_params_->raws_mobile_player_filtering =
      IsInPrimaryMainFrame() && !origin_to_commit.opaque() && !IsPdf() &&
      !commit_params_->is_view_source &&
      GetContentClient()->browser()->ShouldFilterRawSMobilePlayer(
          GetWebContents(), GetURL(), origin_to_commit);

''' + a)
    elif path in (NAV_CONTROLLER, NAV_ENTRY):
        a = '          /*raws_page_text_policy=*/100);'
        text = once(text, a, '''          /*raws_page_text_policy=*/100,
          /*raws_mobile_player_filtering=*/false);''')
    elif path == NAV_MOJOM:
        a = '  int32 raws_page_text_policy = 100;'
        text = once(text, a, a + '\n  bool raws_mobile_player_filtering = false;')
    elif path == CONTENT_H:
        a = '  virtual int GetRawSPageTextPolicyForNavigation(WebContents* web_contents);'
        text = once(text, a, a + '''
  // A single browser-authored decision for issuance with a new navigation.
  virtual bool ShouldFilterRawSMobilePlayer(WebContents* web_contents,
                                           const GURL& url,
                                           const url::Origin& final_origin);
''')
    elif path == CONTENT_CC:
        a = 'int ContentBrowserClient::GetRawSPageTextPolicyForNavigation('
        text = once(text, a, '''bool ContentBrowserClient::ShouldFilterRawSMobilePlayer(
    WebContents*, const GURL&, const url::Origin&) {
  return false;
}

''' + a)
    elif path == CHROME_H:
        a = '  int GetRawSPageTextPolicyForNavigation('
        text = once(text, a, '''  bool ShouldFilterRawSMobilePlayer(
      content::WebContents* web_contents,
      const GURL& url,
      const url::Origin& final_origin) override;
''' + a)
    elif path == CHROME_CC:
        a = 'int ChromeContentBrowserClient::GetRawSPageTextPolicyForNavigation('
        text = once(text, a, '''bool ChromeContentBrowserClient::ShouldFilterRawSMobilePlayer(
    content::WebContents* web_contents,
    const GURL& url,
    const url::Origin& final_origin) {
#if BUILDFLAG(IS_ANDROID)
  if (web_contents && url.SchemeIs("https") && url.host() == "m.youtube.com" &&
      !url.has_username() && !url.has_password() && !url.has_port() &&
      final_origin.IsSameOriginWith(url::Origin::Create(url))) {
    return sandium::adblock_native::IsSiteAdsEnabled(
        web_contents->GetBrowserContext(), final_origin);
  }
#endif
  return false;
}

''' + a)
    elif path == RENDER_FRAME:
        a = '  navigation_params->raws_page_text_policy = commit_params.raws_page_text_policy;'
        text = once(text, a, a + '''
  navigation_params->raws_mobile_player_filtering =
      commit_params.raws_mobile_player_filtering;''')
    elif path == WEB_PARAMS:
        a = '  int32_t raws_page_text_policy = 100;'
        text = once(text, a, a + '\n  bool raws_mobile_player_filtering = false;')
    elif path == PUBLIC_LOADER:
        a = '  virtual WebURL GetUrl() const = 0;'
        text = once(text, a, a + '\n  virtual bool RawSMobilePlayerFiltering() const;')
    elif path == LOADER_H:
        a = '  WebURL GetUrl() const override { return Url(); }'
        text = once(text, a, a + '\n  bool RawSMobilePlayerFiltering() const override;')
        a = '  bool force_new_document_sequence_number_ = false;'
        text = once(text, a, a + '\n  const bool raws_mobile_player_filtering_;')
    elif path == LOADER_CC:
        a = '  bool force_new_document_sequence_number;'
        text = once(text, a, a + '\n  bool raws_mobile_player_filtering;')
        a = '          params_->force_new_document_sequence_number),'
        text = once(text, a, a + '''
      raws_mobile_player_filtering_(params_->raws_mobile_player_filtering),''')
        a = 'bool WebDocumentLoader::WillLoadUrlAsEmpty(const WebURL& url) {'
        text = once(text, a, '''bool WebDocumentLoader::RawSMobilePlayerFiltering() const {
  return false;
}

bool DocumentLoader::RawSMobilePlayerFiltering() const {
  return raws_mobile_player_filtering_;
}

''' + a)
    elif path == WIRE:
        a = '                                 url.mojom.Url expected_url, string css);\n};'
        text = once(text, a, a[:-2] + '''  [EnableIf=is_android]
  StopRawSMobilePlayerFiltering(mojo_base.mojom.UnguessableToken document);
};''')
    elif path == HEADER:
        a = '  void SetRawSProceduralCosmetic('
        text = once(text, a, '''  void StopRawSMobilePlayerFiltering(const base::UnguessableToken&) override;
''' + a)
    elif path == BROWSER:
        a = '  RefreshProceduralCosmetic(frame);\n  if (!IsFrameSiteAdsEnabled(frame)) {'
        text = once(text, a, a + '''
    // An explicit disable can stop future pruning in the active document.
    // Enabling is never installed by late IPC; reload starts another commit.
    if (frame.IsInPrimaryMainFrame() &&
        frame.GetLastCommittedOrigin().Serialize() == "https://m.youtube.com") {
      if (auto document = frame.GetEmbeddingToken()) {
        mojo::AssociatedRemote<chrome::mojom::ChromeRenderFrame> remote;
        frame.GetRemoteAssociatedInterfaces()->GetInterface(&remote);
        remote->StopRawSMobilePlayerFiltering(*document);
      }
    }''')
    elif path == RENDERER:
        js = Path(__file__).with_name('player.js').read_text()
        if ')RAWSMW"' in js:
            raise ValueError('raw-string delimiter in script')
        a = 'void ChromeRenderFrameObserver::ReadyToCommitNavigation(\n'
        text = once(text, a, '''#if BUILDFLAG(IS_ANDROID)
namespace {
void RunRawSMobilePlayerFiltering(blink::WebLocalFrame& frame, bool enabled) {
  if (frame.Parent() || frame.IsInFencedFrameTree() || frame.IsProvisional())
    return;
  const auto doc = frame.GetDocument();
  if (doc.IsNull() || !doc.IsActive() || !doc.IsHTMLDocument()) return;
  const GURL url(doc.Url());
  if (!url.SchemeIs("https") || url.host() != "m.youtube.com" ||
      url.has_username() || url.has_password() || url.has_port()) return;
  static constexpr char kPlayer[] = R"RAWSMW(''' + js + ''')RAWSMW";
  const blink::WebScriptSource sources[] = {blink::WebScriptSource(
      blink::WebString::FromUtf8(base::StrCat(
          {kPlayer, enabled ? "(true," : "(false,", "'https://m.youtube.com')"})))};
  frame.RequestExecuteScript(
      0, sources, blink::mojom::UserActivationOption::kDoNotActivate,
      blink::mojom::EvaluationTiming::kSynchronous,
      blink::mojom::LoadEventBlockingOption::kDoNotBlock,
      blink::WebScriptExecutionCallback(), blink::BackForwardCacheAware::kAllow,
      blink::mojom::WantResultOption::kNoResult,
      blink::mojom::PromiseResultOption::kDoNotWait, blink::WebString());
}
}  // namespace
#endif  // BUILDFLAG(IS_ANDROID)

''' + a)
        a = '    WebDocumentLoader* document_loader) {\n  // Execute cache clear operations'
        text = once(text, a, '''    WebDocumentLoader* document_loader) {
#if BUILDFLAG(IS_ANDROID)
  // DispatchDidCommitLoad reaches this renderer observer before Blink opens
  // the response parser. This decision belongs to this exact loader.
  if (document_loader && document_loader->RawSMobilePlayerFiltering() &&
      render_frame()->IsMainFrame()) {
    auto* frame = render_frame()->GetWebFrame();
    if (frame && frame->GetDocumentLoader() == document_loader)
      RunRawSMobilePlayerFiltering(*frame, /*enabled=*/true);
  }
#endif
  // Execute cache clear operations''')
        a = 'void ChromeRenderFrameObserver::SetRawSProceduralCosmetic('
        text = once(text, a, '''void ChromeRenderFrameObserver::StopRawSMobilePlayerFiltering(
    const base::UnguessableToken& token) {
  auto* frame = render_frame()->GetWebFrame();
  if (frame && render_frame()->IsMainFrame() &&
      frame->GetEmbeddingToken() == token &&
      frame->GetDocumentLoader() &&
      frame->GetDocumentLoader()->RawSMobilePlayerFiltering()) {
    RunRawSMobilePlayerFiltering(*frame, /*enabled=*/false);
  }
}

''' + a)
    else:
        raise ValueError('unexpected owner: ' + path)
    return text.encode()
