#!/usr/bin/env python3
"""Browser commit-policy observation, never a renderer/visible-frame assertion."""
PATH = 'content/browser/renderer_host/navigation_request.cc'
ANCHOR = '  GetRenderFrameHost()->CommitNavigation(\n      this, std::move(common_params), std::move(commit_params),'
BODY = '''
  // SANDIUM_DIAGNOSTIC_TYPOGRAPHY_DISPATCH_V1: final inherited/resolved policy.
  if (GetContentClient()->browser()->IsSandiumNavigationDiagnosticsEnabled(GetWebContents())) {
    GetContentClient()->browser()->RecordSandiumNavigationDiagnostic(
        GetWebContents(), 26, GetNavigationId(),
        base::TimeTicks::Now().since_origin().InMicroseconds(),
        {static_cast<double>(commit_params->sandium_page_text_policy),
         IsInOutermostMainFrame() ? 1. : 0., 0.});
  }
'''
def transform(source):
    replacement = BODY + ANCHOR
    if source.count(replacement) == 1:
        return source
    if source.count(ANCHOR) != 1 or 'SANDIUM_DIAGNOSTIC_TYPOGRAPHY_DISPATCH_V1' in source:
        raise ValueError('Typography diagnostic anchor drift or partial overlay')
    return source.replace(ANCHOR, replacement, 1)

if __name__ == '__main__':
    import argparse
    from pathlib import Path
    p = argparse.ArgumentParser()
    p.add_argument('source', type=Path)
    p.add_argument('--apply', action='store_true')
    args = p.parse_args()
    target = args.source / PATH
    result = transform(target.read_text())
    if args.apply:
        target.write_text(result)
    print('Typography dispatch diagnostic plan valid')
