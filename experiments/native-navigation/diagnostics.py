"""Rebase numeric probes onto pinned Chromium without changing navigation decisions.
The journal retains diagnosed product preimages, so rollback precedes normal probe reset.
"""
import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
s=importlib.util.spec_from_file_location('transition_probe_native',ROOT/'experiments/native-transition-diagnostics/apply.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
PATHS=(m.BLUR,m.BACK)
def changes():
 out=[]
 for path,old,new in m.CHANGES:
  if path==m.BLUR and ('SandiumOrdinaryBlurSource' in old or 'pixels->SetPosition' in old):continue
  # The pinned delegate has no custom top-controls method. Report unknown, not zero.
  new=new.replace('GetWebContentsViewAndroidDelegate() ? GetWebContentsViewAndroidDelegate()->GetTopControlsHeight() : 0','-1').replace('delegate->GetTopControlsHeight()','-1')
  if path==m.BLUR and old=='#include "base/metrics/histogram_functions.h"':
   new+='\n#include "content/public/browser/content_browser_client.h"\n#include "content/public/common/content_client.h"'
  out.append((path,old,new))
 return out
NATIVE_CHANGES=changes()
def strip(path,text,items=m.CHANGES):
 for name,old,new in reversed(items):
  if name==path and new in text:
   if text.count(new)!=1:raise ValueError('Duplicate transition probe')
   text=text.replace(new,old,1)
 if 'SANDIUM_TRANSITION_RING_V1' in text:raise ValueError('Unrecognized transition diagnostic probe')
 return text

def apply(path,text):
 for name,old,new in NATIVE_CHANGES:
  if path!=name:continue
  if text.count(old)!=1:raise ValueError('Native diagnostic anchor drift: '+old[:90])
  text=text.replace(old,new,1)
 return text
