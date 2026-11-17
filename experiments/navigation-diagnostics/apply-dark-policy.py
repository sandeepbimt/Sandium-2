#!/usr/bin/env python3
"""Browser commit-policy dispatch evidence, NOT renderer applied/painted acknowledgement."""
from pathlib import Path
PATH='content/browser/renderer_host/navigation_request.cc'
OLD='''    commit_params->sandium_dark_page_flags =
        GetContentClient()->browser()->GetSandiumDarkPageFlagsForNavigation(
            GetWebContents(), common_params->url);
  }'''
NEW=OLD+'''
  // SANDIUM_DIAGNOSTIC_DARK_DISPATCH_V1: policy sent, not paint acknowledgement.
  if (GetContentClient()->browser()->IsSandiumNavigationDiagnosticsEnabled(GetWebContents())) {
    GetContentClient()->browser()->RecordSandiumNavigationDiagnostic(
        GetWebContents(), 7, GetNavigationId(),
        base::TimeTicks::Now().since_origin().InMicroseconds(),
        {static_cast<double>(commit_params->sandium_dark_page_flags), 0.,
         IsInOutermostMainFrame() ? 1. : 0.});
  }
'''
def transform(s):
 if NEW in s:return s
 if s.count(OLD)!=1:raise ValueError('Dark dispatch diagnostic anchor drift')
 return s.replace(OLD,NEW,1)
