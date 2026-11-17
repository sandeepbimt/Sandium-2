#!/usr/bin/env python3
"""Record actual redirect throttle decisions before request may self-destruct."""
from pathlib import Path
PATH='content/browser/renderer_host/navigation_request.cc'
OLD='''void NavigationRequest::OnRedirectChecksComplete(
    NavigationThrottle::ThrottleCheckResult result) {'''
NEW=OLD+'''
  // SANDIUM_DIAGNOSTIC_REDIRECT_RESULT_V1: no URL or header payload.
  auto* sandium_diagnostic_client = GetContentClient()->browser();
  if (sandium_diagnostic_client->IsSandiumNavigationDiagnosticsEnabled(GetWebContents())) {
    sandium_diagnostic_client->RecordSandiumNavigationDiagnostic(
        GetWebContents(), 19, GetNavigationId(),
        base::TimeTicks::Now().since_origin().InMicroseconds(),
        {static_cast<double>(result.action()), static_cast<double>(result.net_error_code())});
  }
'''
def transform(s):
 if NEW in s:return s
 if s.count(OLD)!=1:raise ValueError('Redirect diagnostic anchor drift')
 return s.replace(OLD,NEW,1)
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('--apply',action='store_true');a=p.parse_args();target=a.source/PATH;out=transform(target.read_text())
 if a.apply:target.write_text(out)
 print('Redirect diagnostic plan valid')
