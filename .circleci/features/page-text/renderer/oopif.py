#!/usr/bin/env python3
"""Pinned ordinary-subframe propagation after page-text renderer/apply.py.

No current-preference lookup for child loads. PageImpl owns the accepted main
document snapshot; Blink local roots install it before their fresh documents.
Fenced/guest inner main pages are separate Pages and retain default/own policy.
Not CI activated and not a full Chromium compile/runtime validation.
"""
from pathlib import Path
import argparse

PATCHES = []
def patch(path, old, new): PATCHES.append((path, old, new))

patch('content/browser/renderer_host/page_impl.h',
      '  RenderFrameHostImpl& GetMainDocument() const;',
      '''  RenderFrameHostImpl& GetMainDocument() const;

  // Browser-owned snapshot of the accepted main document, not live preferences.
  // PageImpl lifetime naturally retains it during BFCache/prerender activation.
  int sandium_page_text_policy() const { return sandium_page_text_policy_; }
  void SetSandiumPageTextPolicyForNewDocument(int packed) {
    const int percent = packed & 255;
    sandium_page_text_policy_ =
        packed >= 0 && (packed & ~1023) == 0 && percent >= 75 &&
                percent <= 150 && percent % 5 == 0 ? packed : 100;
  }''')
patch('content/browser/renderer_host/page_impl.h',
      '  const raw_ref<RenderFrameHostImpl> main_document_;',
      '''  const raw_ref<RenderFrameHostImpl> main_document_;

  int sandium_page_text_policy_ = 100;''')
patch('content/browser/renderer_host/navigation_request.cc',
      '''            GetWebContents(), common_params->url);
  }
  commit_params->sandium_dark_page_flags = -1;''',
      '''            GetWebContents(), common_params->url);
  } else if (RenderFrameHostImpl* parent = frame_tree_node_->parent()) {
    // Ordinary local/OOPIF child: inherit this parent's owning Page snapshot.
    // Saved preferences may already differ, but the displayed document must not.
    commit_params->sandium_page_text_policy =
        parent->GetPage().sandium_page_text_policy();
  }
  // The outgoing IPC uses a clone; retain the browser-owned value for accepted
  // main-document commit. Never capture it from renderer-controlled reply data.
  commit_params_->sandium_page_text_policy = commit_params->sandium_page_text_policy;
  commit_params->sandium_dark_page_flags = -1;''')
patch('content/browser/renderer_host/navigation_request.cc',
      """  GetRenderFrameHost()->FailedNavigation(
      this, *common_params_, *commit_params_, has_stale_copy_in_cache_,""",
      """  // Keep the accepted Page snapshot and outgoing failed commit identical.
  // FailedNavigation clones these params; changing only its IPC clone would
  // leave the canonical request policy stale for accepted main-document capture.
  RenderFrameHostImpl* text_policy_parent = frame_tree_node_->parent();
  commit_params_->sandium_page_text_policy =
      text_policy_parent ? text_policy_parent->GetPage().sandium_page_text_policy()
                         : 100;
  GetRenderFrameHost()->FailedNavigation(
      this, *common_params_, *commit_params_, has_stale_copy_in_cache_,""")
patch('content/browser/renderer_host/render_frame_host_impl.cc',
      '''    document_associated_data_->set_navigation_confidence(
        navigation_request->navigation_confidence());''',
      '''    if (is_main_frame()) {
      // This branch runs only for accepted new documents, after per-document
      // state has been replaced. Same-document and Page activations skip it.
      GetPage().SetSandiumPageTextPolicyForNewDocument(
          navigation_request->commit_params().sandium_page_text_policy);
    }

    document_associated_data_->set_navigation_confidence(
        navigation_request->navigation_confidence());''')
patch('content/browser/renderer_host/render_frame_host_impl.cc',
      '''  CHECK_NE(net::OK, error_code);
  UpdateOrDisableCompositorMetricRecorder();''',
      '''  CHECK_NE(net::OK, error_code);
  // A failed child navigation must not reset shared OOPIF Page settings to 100
  // and consequently restyle unrelated sibling documents in that renderer.
  commit_params->sandium_page_text_policy =
      GetParent() ? GetParent()->GetPage().sandium_page_text_policy() : 100;
  UpdateOrDisableCompositorMetricRecorder();''')
patch('third_party/blink/renderer/core/loader/frame_loader.cc',
      '''      // Same fresh-document commit boundary, independent from dark appearance.
      settings->SetSandiumPageTextPolicyForCommit(navigation_params->sandium_page_text_policy);
      const int policy = navigation_params->sandium_dark_page_flags;''',
      '''      const int policy = navigation_params->sandium_dark_page_flags;''')
patch('third_party/blink/renderer/core/loader/frame_loader.cc',
      '''  // The outgoing document and its unload handlers have finished, and a
  // provisional frame has successfully swapped in. Apply policy before the new''',
      '''  // Main and OOPIF local roots each have renderer-local Page Settings.
  // The browser sends one captured owning-page policy to every ordinary child.
  // Local descendants inherit this setting; they must not mutate shared Settings.
  if (commit_reason == CommitReason::kRegular && frame_->IsLocalRoot()) {
    if (Settings* settings = frame_->GetSettings()) {
      settings->SetSandiumPageTextPolicyForCommit(navigation_params->sandium_page_text_policy);
    }
  }

  // The outgoing document and its unload handlers have finished, and a
  // provisional frame has successfully swapped in. Apply policy before the new''')
patch('third_party/blink/renderer/core/dom/document.cc',
      '''      GetFrame()->IsOutermostMainFrame() && Url().ProtocolIsInHTTPFamily()) {''',
      '''      (Url().ProtocolIsInHTTPFamily() ||
       (GetFrame()->Tree().Parent() &&
        (Url().IsAboutBlankUrl() || Url().IsAboutSrcdocUrl())))) {''')

def apply(root):
    root = Path(root)
    staged = {}
    for relative, old, new in PATCHES:
        path = root/relative
        source = staged.get(path, path.read_text())
        # Removal replacements are subsets of their anchors.
        if new in source and not (new in old and old in source): continue
        if source.count(old) != 1:
            raise ValueError('Page-text OOPIF pinned anchor mismatch: '+relative+': '+old[:90])
        staged[path] = source.replace(old,new,1)
    for path, source in staged.items(): path.write_text(source)
    return len(staged)

if __name__ == '__main__':
    p = argparse.ArgumentParser();p.add_argument('source_root',type=Path)
    print(apply(p.parse_args().source_root))
