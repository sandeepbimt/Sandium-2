#!/usr/bin/env python3
"""Pinned page-text native composition. NOT wired into production CI yet.

Run after dark-pages renderer composition. No active-document preference updates,
toolbar hooks, DOM observers or BFCache activation changes. Tests distinguish
source composition from actual Chromium compilation/rendering.
"""
import argparse
from pathlib import Path

PIN = 'd331de35ca8ab1358c7a17e4bd41627d55eaef51'
PATCHES = []
def patch(path, old, new):
    PATCHES.append((path, old, new))

patch('chrome/browser/android/web_contents_theme_client.h',
      '  int SandiumDarkPageFlags(const GURL& document_url);',
      '  int SandiumDarkPageFlags(const GURL& document_url);\n'
      '  int SandiumPageTextPolicy(const GURL& document_url);')
patch('chrome/browser/android/web_contents_theme_client.cc',
      '}  // namespace night_mode', '''int WebContentsThemeClient::SandiumPageTextPolicy(const GURL& document_url) {
  JNIEnv* env = base::android::AttachCurrentThread();
  return Java_WebContentsThemeClient_sandiumPageTextPolicy(env, &GetWebContents(), document_url);
}

}  // namespace night_mode''')
patch('content/public/browser/content_browser_client.h',
      '  virtual int GetSandiumDarkPageFlagsForNavigation(',
      '''  // Independent document-bound typography. 100 means native website baseline.
  virtual int GetSandiumPageTextPolicyForNavigation(
      WebContents* web_contents, const GURL& document_url);

  virtual int GetSandiumDarkPageFlagsForNavigation(''')
patch('content/public/browser/content_browser_client.cc',
      'int ContentBrowserClient::GetSandiumDarkPageFlagsForNavigation(',
      '''int ContentBrowserClient::GetSandiumPageTextPolicyForNavigation(
    WebContents* web_contents, const GURL& document_url) {
  return 100;
}

int ContentBrowserClient::GetSandiumDarkPageFlagsForNavigation(''')
patch('chrome/browser/chrome_content_browser_client.h',
      '  int GetSandiumDarkPageFlagsForNavigation(',
      '''  int GetSandiumPageTextPolicyForNavigation(
      content::WebContents* web_contents, const GURL& document_url) override;
  int GetSandiumDarkPageFlagsForNavigation(''')
patch('chrome/browser/chrome_content_browser_client.cc',
      'int ChromeContentBrowserClient::GetSandiumDarkPageFlagsForNavigation(',
      '''int ChromeContentBrowserClient::GetSandiumPageTextPolicyForNavigation(
    WebContents* web_contents, const GURL& document_url) {
#if BUILDFLAG(IS_ANDROID)
  if (web_contents && document_url.SchemeIsHTTPOrHTTPS()) {
    if (auto* client = night_mode::WebContentsThemeClient::FromWebContents(web_contents))
      return client->SandiumPageTextPolicy(document_url);
  }
#endif
  return 100;
}

int ChromeContentBrowserClient::GetSandiumDarkPageFlagsForNavigation(''')
patch('third_party/blink/public/mojom/navigation/navigation_params.mojom',
      '  int32 sandium_dark_page_flags = -1;',
      '''  int32 sandium_dark_page_flags = -1;
  // Low byte: independent text percentage; bits8/9: typography enabled/justify.
  int32 sandium_page_text_policy = 100;''')
patch('content/browser/renderer_host/navigation_request.cc',
      '  commit_params->sandium_dark_page_flags = -1;',
      '''  // Default first, including internal/error/opaque/view-source destinations.
  commit_params->sandium_page_text_policy = 100;
  if (IsInOutermostMainFrame() && !origin_to_commit.opaque() &&
      common_params->url.SchemeIsHTTPOrHTTPS() && !commit_params->is_view_source) {
    commit_params->sandium_page_text_policy =
        GetContentClient()->browser()->GetSandiumPageTextPolicyForNavigation(
            GetWebContents(), common_params->url);
  }
  commit_params->sandium_dark_page_flags = -1;''')
patch('third_party/blink/public/web/web_navigation_params.h',
      '  int sandium_dark_page_flags = -1;',
      '  int sandium_dark_page_flags = -1;\n  int sandium_page_text_policy = 100;')
patch('content/renderer/render_frame_impl.cc',
      '  navigation_params->sandium_dark_page_flags = commit_params.sandium_dark_page_flags;',
      '''  navigation_params->sandium_page_text_policy = commit_params.sandium_page_text_policy;
  navigation_params->sandium_dark_page_flags = commit_params.sandium_dark_page_flags;''')
patch('third_party/blink/renderer/core/loader/frame_loader.cc',
      '      const int policy = navigation_params->sandium_dark_page_flags;',
      '''      // Same fresh-document commit boundary, independent from dark appearance.
      settings->SetSandiumPageTextPolicyForCommit(navigation_params->sandium_page_text_policy);
      const int policy = navigation_params->sandium_dark_page_flags;''')
patch('third_party/blink/renderer/core/frame/settings.json5',
      '      name: "accessibilityFontScaleFactor",',
      '''      name: "sandiumPageTextPolicy",
      initial: "100",
      type: "int",
    },
    {
      name: "accessibilityFontScaleFactor",''')
patch('third_party/blink/renderer/build/scripts/templates/settings_base.h.tmpl',
      '  void SetFromStrings(const String& name, const String& value);',
      '''  // Only FrameLoader's post-detach/pre-install commit path may change this.
  // Never reinterpret native accessibility settings or mutate a cached document.
  void SetSandiumPageTextPolicyForCommit(int packed) {
    const int percent = packed & 255;
    sandium_page_text_policy_ =
        packed >= 0 && (packed & ~1023) == 0 && percent >= 75 &&
                percent <= 150 && percent % 5 == 0 ? packed : 100;
  }
  int SandiumPageTextScalePercent() const {
    return sandium_page_text_policy_ & 255;
  }
  bool SandiumPageTextJustifyEnabled() const {
    return (sandium_page_text_policy_ & 768) == 768;
  }

  void SetFromStrings(const String& name, const String& value);''')
for path in ('content/browser/renderer_host/navigation_entry_impl.cc',
             'content/browser/renderer_host/navigation_controller_impl.cc',
             'content/browser/renderer_host/navigation_request.cc'):
    patch(path, '          /*sandium_dark_page_flags=*/-1, url::Origin(),',
          '          /*sandium_dark_page_flags=*/-1, /*sandium_page_text_policy=*/100, url::Origin(),')

patch('third_party/blink/renderer/core/dom/document.cc',
      '#include "third_party/blink/renderer/core/css/parser/css_parser.h"',
      '''#include "third_party/blink/renderer/core/css/parser/css_parser.h"
#include "third_party/blink/renderer/core/css/parser/css_parser_context.h"
#include "third_party/blink/public/web/web_css_origin.h"
#include "third_party/blink/renderer/platform/wtf/text/string_builder.h"''')

EXCLUDED = ('nav,header,footer,aside,form,button,textarea,input,select,figure,table,pre,code,'
            '[role=navigation],[role=button],[role=textbox],[role=dialog],'
            '[contenteditable]:not([contenteditable=false]),[aria-hidden=true],.comments,#comments')
CSS = (':where(article,[role=article],[itemprop=articleBody]) p'
       ':not(:where(' + EXCLUDED + ')):not(:where(' + EXCLUDED + ') *)'
       '{text-align:justify !important;}')
patch('third_party/blink/renderer/core/dom/document.cc',
      '''  UpdateForcedColors();
  const ComputedStyle& style = GetStyleResolver().StyleForViewport();''',
      '''  // One native user sheet before initial viewport/content style. No JS,
  // observer, page hiding or load-finished callback. Default OFF installs none.
  if (const Settings* settings = GetSettings();
      settings && (settings->SandiumPageTextJustifyEnabled() ||
                   settings->SandiumPageTextScalePercent() != 100) &&
      GetFrame()->IsOutermostMainFrame() && Url().ProtocolIsInHttpFamily()) {
    StringBuilder css;
    if (settings->SandiumPageTextScalePercent() != 100 &&
        settings->GetTextSizeAdjustEnabled()) {
      css.Append("*{-webkit-text-size-adjust:");
      css.AppendNumber(settings->SandiumPageTextScalePercent());
      css.Append("% !important;text-size-adjust:");
      css.AppendNumber(settings->SandiumPageTextScalePercent());
      css.Append("% !important;}");
    }
    if (settings->SandiumPageTextJustifyEnabled())
      css.Append(R"sandium(''' + CSS + ''')sandium");
    if (!css.empty()) {
      auto* sheet = MakeGarbageCollected<StyleSheetContents>(
          MakeGarbageCollected<CSSParserContext>(*this));
      sheet->ParseString(css.ToString());
      GetStyleEngine().InjectSheet(AtomicString("sandium-page-text-v1"), sheet,
                                  WebCssOrigin::kUser);
    }
  }
  UpdateForcedColors();
  const ComputedStyle& style = GetStyleResolver().StyleForViewport();''')

def apply(root):
    root = Path(root)
    staged = {}
    for relative, old, new in PATCHES:
        path = root / relative
        source = staged.get(path, path.read_text())
        expected = 2 if relative.endswith('/navigation_request.cc') and old.startswith(
            '          /*sandium_dark_page_flags=*/-1, url::Origin(),') else 1
        if source.count(new) == expected:
            continue
        if source.count(old) != expected:
            raise ValueError('Page-text pinned anchor mismatch: ' + relative + ': ' + old[:80])
        staged[path] = source.replace(old, new)
    for path, source in staged.items():
        path.write_text(source)
    return len(staged)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source_root', type=Path)
    print(apply(parser.parse_args().source_root))
