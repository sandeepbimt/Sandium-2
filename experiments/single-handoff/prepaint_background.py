"""Pinned156 temporary canvas candidate, not a proven white-flash fix.

Native blur/Off/Low, paint holding, compositor ownership and geometry unchanged.
No screenshot cover, loading wait, timer or forced darkening of painted pages.
"""
from pathlib import Path
import gzip
import hashlib
PATH = 'chrome/browser/android/tab_android.cc'
FIX = Path(__file__).parent/'fixtures/prepaint-background-156/tab_android.cc.gz'
BLOB = 'dc12c8e4e232f717b9a6087ee8fcc04e1b832ae5'
HELPER = '// BSD 3-Clause License\n// \n// Copyright (c) 2026 Bare contributors\n// \n// Redistribution and use in source and binary forms, with or without\n// modification, are permitted provided that the following conditions are met:\n// \n// 1. Redistributions of source code must retain the above copyright notice, this\n//    list of conditions and the following disclaimer.\n// \n// 2. Redistributions in binary form must reproduce the above copyright notice,\n//    this list of conditions and the following disclaimer in the documentation\n//    and/or other materials provided with the distribution.\n// \n// 3. Neither the name of the copyright holder nor the names of its\n//    contributors may be used to endorse or promote products derived from\n//    this software without specific prior written permission.\n// \n// THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"\n// AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE\n// IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE\n// DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE\n// FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL\n// DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR\n// SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER\n// CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,\n// OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE\n// OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.\n\n' + '// SANDIUM_PREPAINT_BACKGROUND_156: temporary renderer canvas, never an overlay.\n// Based on BareBrowser patch 0186; a light document gets its default canvas back.\nclass SandiumPrePaintBackground\n    : public content::WebContentsObserver,\n      public content::WebContentsUserData<SandiumPrePaintBackground> {\n public:\n  SandiumPrePaintBackground(const SandiumPrePaintBackground&) = delete;\n  SandiumPrePaintBackground& operator=(const SandiumPrePaintBackground&) = delete;\n  ~SandiumPrePaintBackground() override = default;\n\n private:\n  explicit SandiumPrePaintBackground(content::WebContents* contents)\n      : content::WebContentsObserver(contents),\n        content::WebContentsUserData<SandiumPrePaintBackground>(*contents) {}\n  friend class content::WebContentsUserData<SandiumPrePaintBackground>;\n\n  void Release() {\n    if (!holding_) return;\n    holding_ = false;\n    web_contents()->SetPageBaseBackgroundColor(std::nullopt);\n  }\n\n  void DidStartNavigation(content::NavigationHandle* handle) override {\n    if (handle->IsInPrimaryMainFrame() && !handle->IsSameDocument()) Release();\n  }\n\n  void DidFinishNavigation(content::NavigationHandle* handle) override {\n    if (!handle->IsInPrimaryMainFrame() || handle->IsSameDocument() ||\n        !handle->HasCommitted()) return;\n    // A late cancellation of an older request must not release the newer page.\n    Release();\n    // Do not recolor an already-painted restored page, native UI or an error.\n    if (handle->IsErrorPage() ||\n        handle->IsServedFromBackForwardCache() ||\n        handle->IsPrerenderedPageActivation() ||\n        !handle->GetURL().SchemeIsHTTPOrHTTPS() ||\n        web_contents()->GetVisibility() != content::Visibility::VISIBLE) return;\n    auto* theme =\n        night_mode::WebContentsThemeClient::FromWebContents(web_contents());\n    if (theme && theme->IsNightModeEnabled()) {\n      holding_ = true;\n      web_contents()->SetPageBaseBackgroundColor(SK_ColorBLACK);\n    }\n  }\n\n  void DidFirstVisuallyNonEmptyPaint() override { Release(); }\n  // Also cover empty documents, cancelled loading, tab hiding and renderer loss.\n  void DidStopLoading() override {\n    // This event is frame-tree-wide, not navigation-scoped. An earlier observer\n    // can synchronously start another load while the stop event is dispatched.\n    if (!web_contents()->IsLoading()) Release();\n  }\n  void OnVisibilityChanged(content::Visibility visibility) override {\n    if (visibility != content::Visibility::VISIBLE) Release();\n  }\n  void PrimaryMainFrameRenderProcessGone(base::TerminationStatus status) override {\n    Release();\n  }\n  void WebContentsDestroyed() override {\n    // No renderer mutation during destruction; userdata dies with WebContents.\n    holding_ = false;\n  }\n\n  bool holding_ = false;\n  WEB_CONTENTS_USER_DATA_KEY_DECL();\n};\n\nWEB_CONTENTS_USER_DATA_KEY_IMPL(SandiumPrePaintBackground);\n\n'
ANCHOR = '  night_mode::WebContentsThemeClient::CreateForWebContents(web_contents_.get());\n'
INSTALL = ANCHOR + '\n  SandiumPrePaintBackground::CreateForWebContents(web_contents_.get());\n'

def fixture():
    data=gzip.decompress(FIX.read_bytes())
    if hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()!=BLOB:
        raise ValueError('Pinned156 tab source fixture hash mismatch')
    return data.decode()

def transform(text):
    original=fixture()
    wanted=original.replace('#include <cstdint>', '#include <cstdint>\n#include <optional>')
    wanted=wanted.replace('#include "content/public/browser/navigation_entry.h"',
        '#include "content/public/browser/navigation_entry.h"\n#include "content/public/browser/navigation_handle.h"')
    wanted=wanted.replace('#include "ui/android/view_android.h"', '#include "third_party/skia/include/core/SkColor.h"\n#include "ui/android/view_android.h"')
    wanted=wanted.replace('}  // namespace\n',HELPER+'}  // namespace\n',1)
    if wanted.count(ANCHOR)!=1:
        raise ValueError('Pinned156 WebContents initialization anchor drift')
    wanted=wanted.replace(ANCHOR,INSTALL,1)
    if text not in (original,wanted):
        raise ValueError('Unknown tab_android.cc changes; refusing temporary background patch')
    return wanted

def plan(root):
    path=Path(root)/PATH
    return {path:transform(path.read_text())}
