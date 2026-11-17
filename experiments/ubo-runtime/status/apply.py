#!/usr/bin/env python3
"""Read-only visible engine state in existing Shields. Apply after product/runtime overlays."""
import argparse,base64,json,os
from pathlib import Path
import xml.etree.ElementTree as ET
HERE=Path(__file__).resolve().parent
RECEIPT='.sandium-ubo-visible-status.json'
JAVA='android/java/org/chromium/chrome/browser/shields/BraveUnifiedPanelHandler.java'
SETTINGS='android/java/org/chromium/chrome/browser/preferences/website/BraveShieldsContentSettings.java'
NATIVE='browser/android/brave_shields_content_settings.cc'
LAYOUT='android/java/brave-res/layout/brave_shields_tab_content.xml'
BUILD='browser/android/BUILD.gn'
A='{http://schemas.android.com/apk/res/android}'
for prefix,uri in [('android',A[1:-1]),('app','http://schemas.android.com/apk/res-auto'),('tools','http://schemas.android.com/tools')]:ET.register_namespace(prefix,uri)
def once(s,a,b):
 if s.count(a)!=1:raise ValueError('Status anchor mismatch: '+a[:80])
 return s.replace(a,b,1)
def plan(core):
 out={}
 text=(core/JAVA).read_text()
 text=once(text,'    private TextView mShieldsStatusText;', '    private TextView mShieldsStatusText;\n    private TextView mSandiumEngineStatusText;\n    private final Runnable mSandiumEngineStatusRefresh = this::refreshSandiumEngineStatus;')
 text=once(text,'        mShieldsStatusText = popupView.findViewById(R.id.shields_status_text);','        mShieldsStatusText = popupView.findViewById(R.id.shields_status_text);\n        mSandiumEngineStatusText = popupView.findViewById(R.id.sandium_engine_status);')
 text=once(text,'    private void updateValues() {','    private void updateValues() {\n        refreshSandiumEngineStatus();')
 text=once(text,'    private void updateValues() {',(HERE/'java_status.txt').read_text()+'    private void updateValues() {')
 out[JAVA]=text.encode()
 text=(core/SETTINGS).read_text()
 anchor='    @NativeMethods\n    interface Natives {'
 wrapper='    public static int getSandiumBlockingEngineStatus(Profile profile) {\n        if (profile == null) return 5;\n        return BraveShieldsContentSettingsJni.get().getSandiumBlockingEngineStatus(profile);\n    }\n\n'
 text=once(text,anchor,wrapper+anchor+'\n        int getSandiumBlockingEngineStatus(Profile profile);')
 out[SETTINGS]=text.encode()
 text=(core/NATIVE).read_text()
 text=once(text,'#include "brave/browser/android/brave_shields_content_settings.h"','#include "brave/browser/android/brave_shields_content_settings.h"\n#include "base/feature_list.h"\n#include "brave/browser/brave_browser_features.h"\n#include "brave/browser/extensions/api/sandium_ubo_api.h"\n#include "brave/components/sandium_ubo_routing/routing.h"')
 text=once(text,'namespace android {','namespace android {\n\n'+(HERE/'native_status.cc').read_text())
 out[NATIVE]=text.encode()
 # This translation unit is owned by android_browser_process, not extensions.
 # Existing bridge deps are lower-level targets (profiles/settings/content and
 # extensions/browser); do not add //brave/browser/extensions or browser:core.
 text=(core/BUILD).read_text()
 start=text.index('source_set("android_browser_process") {')
 stop=text.index('\nsource_set(',start+1)
 block=text[start:stop]
 block=once(block,'  deps = [','  deps = [\n    "//brave/browser/extensions/api:sandium_ubo_bridge",\n    "//brave/components/sandium_ubo_routing",')
 out[BUILD]=(text[:start]+block+text[stop:]).encode()
 text=(core/LAYOUT).read_text();root=ET.fromstring(text)
 found=False
 for parent in root.iter():
  for index,child in enumerate(list(parent)):
   if child.get(A+'id')!='@+id/shields_status_text':continue
   row=ET.Element('TextView',{A+'id':'@+id/sandium_engine_status',A+'layout_width':'match_parent',A+'layout_height':'wrap_content',A+'minHeight':'32dp',A+'maxLines':'2',A+'textSize':'12sp',A+'textColor':'?attr/colorOnSurfaceVariant',A+'paddingTop':'4dp',A+'importantForAccessibility':'yes',A+'accessibilityLiveRegion':'polite'})
   parent.insert(index+1,row);found=True;break
 if not found:raise ValueError('Missing Shields status layout')
 ET.indent(root,space='    ')
 out[LAYOUT]=(text[:text.index('<LinearLayout')]+ET.tostring(root,encoding='unicode')+'\n').encode()
 return out
def path(core,name):
 p=core/name
 if Path(name).is_absolute() or '..' in Path(name).parts or p.is_symlink():raise ValueError('Unsafe status path')
 return p
def write(p,b):
 t=p.with_name(p.name+'.status-tmp');t.write_bytes(b);os.replace(t,p)
def transition(core,r,key):
 checked=[]
 for name,pair in r.items():
  p=path(core,name);before=base64.b64decode(pair['before']);after=base64.b64decode(pair['after'])
  if p.read_bytes() not in (before,after):raise ValueError('Unowned status change: '+name)
  checked.append((p,base64.b64decode(pair[key])))
 for p,b in checked:write(p,b)
def apply(core):
 r=core/RECEIPT
 if r.exists():transition(core,json.loads(r.read_text()),'after');return
 receipt={n:{'before':base64.b64encode(path(core,n).read_bytes()).decode(),'after':base64.b64encode(b).decode()} for n,b in plan(core).items()}
 write(r,json.dumps(receipt,sort_keys=True).encode());transition(core,receipt,'after')
def reset(core):
 r=core/RECEIPT
 if not r.exists():return
 transition(core,json.loads(r.read_text()),'before');r.unlink()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--core',required=True,type=Path);p.add_argument('--reset',action='store_true');a=p.parse_args();(reset if a.reset else apply)(a.core.resolve())
