#!/usr/bin/env python3
"""Standalone lifecycle producer, not wired until full diagnostics coverage is reviewed."""
from pathlib import Path
PATH='chrome/android/java/src/org/chromium/chrome/browser/tab/TabWebContentsObserver.java'
REC='org.chromium.chrome.browser.sandium.diagnostics.SandiumNavigationDiagnostics'
CHANGES=[]
def add(signature,event,nav,values):
 code=f'''\n            if ({REC}.isRecording() && !mTab.isIncognito()) {{
                {REC}.record({REC}.Event.{event}, {nav}, mTab.isIncognito(), {values});
            }}'''
 CHANGES.append((signature,signature+code))
add('public void didStartNavigationInPrimaryMainFrame(NavigationHandle navigation) {','NAV_START','navigation.getNavigationId()', 'navigation.isRendererInitiated() ? 1 : 0, navigation.isHistory() ? 1 : 0, navigation.isBack() ? 1 : 0, navigation.isForward() ? 1 : 0, navigation.hasUserGesture() ? 1 : 0')
add('public void didRedirectNavigation(NavigationHandle navigation) {','NAV_REDIRECT','navigation.getNavigationId()', 'navigation.isRendererInitiated() ? 1 : 0, navigation.hasUserGesture() ? 1 : 0')
add('public void didFinishNavigationInPrimaryMainFrame(NavigationHandle navigation) {','NAV_FINISH','navigation.getNavigationId()', 'navigation.hasCommitted() ? 1 : 0, navigation.isErrorPage() ? 1 : 0, navigation.errorCode(), navigation.httpStatusCode(), navigation.isDownload() ? 1 : 0')
add('public void didFirstVisuallyNonEmptyPaint() {','FIRST_PAINT','0','1')
add('public void primaryMainFrameRenderProcessGone(@TerminationStatus int terminationStatus) {','RENDERER_EXIT','0','terminationStatus, mTab.isDestroyed() ? 1 : 0')
def transform(s):
 for old,new in CHANGES:
  if new in s:continue
  if s.count(old)!=1:raise ValueError('Lifecycle anchor drift: '+old)
  s=s.replace(old,new,1)
 return s
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('--apply',action='store_true');a=p.parse_args();target=a.source/PATH;out=transform(target.read_text())
 if a.apply:target.write_text(out)
 print('Lifecycle producer plan valid; not production wired')
