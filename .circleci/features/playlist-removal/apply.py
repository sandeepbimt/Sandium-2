#!/usr/bin/env python3
"""Feature-local exact transformations for pinned Android Playlist removal."""
import argparse,json,re
from pathlib import Path
OPS=json.loads(Path(__file__).with_name('operations.json').read_text())
def retired_by_vpn(op, source):
 # VPN's final compile-out removes the sole remaining deeplink conditional.
 # Accept only this exact shared-chain operation and the known empty dispatcher,
 # never arbitrary missing replacements elsewhere.
 if op['anchor'] != 'BraveConstants.DEEPLINK_ANDROID_PLAYLIST': return False
 if 'DEEPLINK_ANDROID_PLAYLIST' in source or 'DEEPLINK_ANDROID_VPN' in source: return False
 return re.search(r'public boolean maybeHandleUrlIntent\(Intent intent\) \{\s*'
                  r'String appLinkAction = intent.getAction\(\);\s*'
                  r'Uri appLinkData = intent.getData\(\);\s*'
                  r'if \(Intent.ACTION_VIEW.equals\(appLinkAction\) && appLinkData != null\) \{\s*'
                  r'String lastPathSegment = appLinkData.getLastPathSegment\(\);\s*\}', source) is not None

def apply(core):
 staged={}
 for op in OPS:
  p=core/op['path'];s=staged.get(p,p.read_text());old,new=op['old'],op['new']
  count=s.count(old)
  if count:
   if count!=op.get('count',1):raise RuntimeError(f"playlist source drift: {op['path']} {op['anchor'][:80]}")
   s=s.replace(old,new)
  elif new and new in s:pass
  elif retired_by_vpn(op,s):pass
  elif not new and op['anchor'] not in s:pass
  else:raise RuntimeError(f"playlist unknown composed source: {op['path']} {op['anchor'][:80]}")
  staged[p]=s
 for p,s in staged.items():p.write_text(s)
 print(f"SANDIUM_PLAYLIST_REMOVAL=APPLIED files={len(staged)} native_flag_required=enable_playlist=false")
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--core',type=Path,required=True);a=p.parse_args();apply(a.core)
