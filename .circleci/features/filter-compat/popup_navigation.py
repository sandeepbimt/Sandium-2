"""Install popup-only native navigation matching over Sandium's media-popup overlay."""
import argparse
from pathlib import Path

HERE = Path(__file__).resolve().parent
WEB = "third_party/blink/public/web/web_window_features.h"
MOJO = "third_party/blink/public/mojom/window_features/window_features.mojom"
CONVERTER = "content/public/renderer/window_features_converter.cc"
DOM = "third_party/blink/renderer/core/frame/local_dom_window.cc"
CREATE = "third_party/blink/renderer/core/page/create_window.cc"
CONTENTS = "content/browser/web_contents/web_contents_impl.cc"
CLIENT = "content/public/browser/content_browser_client.h"
BRAVE_H = "brave/browser/brave_content_browser_client.h"
BRAVE_CC = "brave/browser/brave_content_browser_client.cc"


def before(anchor, extra):
    return (anchor, extra + anchor)


def after(anchor, extra):
    return (anchor, anchor + extra)


def edits():
    implementation = (HERE / "popup_navigation.cc.inc").read_text()
    return {
        WEB: [after("  bool sandium_scripted_media_popup = false;\n",
                    "  bool sandium_scripted_popup = false;\n")],
        MOJO: [after("    bool sandium_scripted_media_popup = false;\n",
                     "    bool sandium_scripted_popup = false;\n")],
        CONVERTER: [
            after("      web_window_features.sandium_scripted_media_popup;\n",
                   "  result->sandium_scripted_popup = web_window_features.sandium_scripted_popup;\n"),
            after("      window_features.sandium_scripted_media_popup;\n",
                  "  result.sandium_scripted_popup = window_features.sandium_scripted_popup;\n"),
        ],
        DOM: [before("  frame_request.SetFeaturesForWindowOpen(window_features);\n",
                     "#if BUILDFLAG(IS_ANDROID)\n  window_features.sandium_scripted_popup = true;\n#endif\n")],
        CREATE: [before("  const auto& picture_in_picture_window_options =\n",
                        """#if BUILDFLAG(IS_ANDROID)
  // Native links and forms keep Chromium's normal behavior. Script-created
  // windows and synthetic anchor clicks can be checked against popup rules.
  if (request.GetClientNavigationReason() == ClientNavigationReason::kAnchorClick &&
      request.GetTriggeringEventInfo() ==
          mojom::blink::TriggeringEventInfo::kFromUntrustedEvent) {
    features.sandium_scripted_popup = true;
  }
#endif
""")],
        CONTENTS: [before("  observers_.NotifyObservers(&WebContentsObserver::DidOpenRequestedURL,\n"
                          "                             new_contents_impl, opener, params.target_url,\n", """#if BUILDFLAG(IS_ANDROID)
  if (params.features->sandium_scripted_popup &&
      !params.is_form_submission &&
      (params.disposition == WindowOpenDisposition::NEW_FOREGROUND_TAB ||
       params.disposition == WindowOpenDisposition::NEW_BACKGROUND_TAB ||
       params.disposition == WindowOpenDisposition::NEW_POPUP ||
       params.disposition == WindowOpenDisposition::NEW_WINDOW)) {
    GetContentClient()->browser()->OnSandiumScriptedPopupCreated(opener, new_contents_impl);
  }
#endif
""")],
        CLIENT: [after("  virtual void OnWebContentsCreated(WebContents* web_contents);\n", """
#if BUILDFLAG(IS_ANDROID)
  virtual void OnSandiumScriptedPopupCreated(RenderFrameHost*, WebContents*) {}
#endif
""")],
        BRAVE_H: [before("  bool CanCreateWindow(content::RenderFrameHost* opener,\n", """#if BUILDFLAG(IS_ANDROID)
  void OnSandiumScriptedPopupCreated(content::RenderFrameHost* opener,
                                     content::WebContents* new_contents) override;
#endif
""")],
        BRAVE_CC: [
            before('#include "brave/browser/brave_account/brave_account_navigation_throttle.h"\n',
                   """#if BUILDFLAG(IS_ANDROID)
#include "base/memory/weak_ptr.h"
#include "base/supports_user_data.h"
#include "base/time/time.h"
#include "base/timer/timer.h"
#include "content/public/browser/navigation_throttle.h"
#include "content/public/browser/navigation_throttle_registry.h"
#include "content/public/browser/web_contents.h"
#endif
"""),
            before("void BraveContentBrowserClient::CreateThrottlesForNavigation(\n", implementation),
            after("  ChromeContentBrowserClient::CreateThrottlesForNavigation(registry);\n",
                  "\n#if BUILDFLAG(IS_ANDROID)\n  SandiumPopupNavigationThrottle::MaybeCreateAndAdd(registry);\n#endif\n"),
        ],
    }


def planned(root):
    result = {}
    for name, replacements in edits().items():
        path = root / name
        original = path.read_text()
        state = []
        for anchor, updated in replacements:
            if original.count(anchor) != 1 or original.count(updated) > 1:
                raise ValueError("Unexpected popup-navigation source in " + name)
            state.append(updated in original)
        if all(state):
            continue
        if any(state) or any(marker in original for marker in
                             ("sandium_scripted_popup", "SandiumPopupNavigationThrottle",
                              "OnSandiumScriptedPopupCreated")):
            raise ValueError("Partial popup-navigation integration in " + name)
        updated = original
        for anchor, replacement in replacements:
            updated = updated.replace(anchor, replacement, 1)
        result[path] = updated
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("src", type=Path)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    changes = planned(args.src)
    if args.verify_only and changes:
        parser.error("popup-navigation integration missing")
    for path, contents in changes.items():
        path.write_text(contents)


if __name__ == "__main__":
    main()
