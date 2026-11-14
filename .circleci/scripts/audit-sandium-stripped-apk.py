#!/usr/bin/env python3
"""Inspect actual DEX class definitions, not incidental string references.
This proves listed feature implementations are absent from DEX, not runtime/network
behavior or native absence. Native dependency closure is a separate mandatory gate.
"""
import argparse,json,struct,zipfile
from pathlib import Path
PREFIXES={
 'vpn':['Lorg/chromium/chrome/browser/vpn/'],
 'wallet':['Lorg/chromium/chrome/browser/crypto_wallet/'],
 'playlist':['Lorg/chromium/chrome/browser/playlist/'],
 'leo':['Lorg/chromium/chrome/browser/ai_chat/','Lorg/chromium/chrome/browser/leo/','Lorg/chromium/chrome/browser/brave_leo/','Lorg/chromium/chrome/browser/settings/BraveLeo','Lorg/chromium/chrome/browser/toolbar/adaptive/BraveLeo','Lorg/chromium/chrome/browser/omnibox/BraveLeo','Lorg/chromium/chrome/browser/omnibox/suggestions/BraveLeo'],
 'news':['Lorg/chromium/chrome/browser/brave_news/','Lorg/chromium/chrome/browser/settings/BraveNews'],
 'rewards_ads':['Lorg/chromium/chrome/browser/rewards/','Lorg/chromium/chrome/browser/ads/'],
}
def u32(d,n):return struct.unpack_from('<I',d,n)[0]
def dex_classes(d):
 if not d.startswith(b'dex\n') or len(d)<112:raise ValueError('Invalid DEX')
 if u32(d,32)!=len(d):raise ValueError('Truncated DEX')
 strings_n,strings=struct.unpack_from('<II',d,56)
 types_n,types=struct.unpack_from('<II',d,64)
 classes_n,classes=struct.unpack_from('<II',d,96)
 def text(index):
  if index>=strings_n:raise ValueError('Invalid string index')
  at=u32(d,strings+4*index)
  for _ in range(5):
   b=d[at];at+=1
   if b<128:break
  else:raise ValueError('Invalid ULEB128')
  return d[at:d.index(b'\0',at)].decode('utf-8')
 result=[]
 for n in range(classes_n):
  t=u32(d,classes+32*n)
  if t>=types_n:raise ValueError('Invalid class type')
  result.append(text(u32(d,types+4*t)))
 return result

def audit(apk):
 with zipfile.ZipFile(apk) as z:
  names=z.namelist();dex=[n for n in names if n.endswith('.dex')]
  if not dex:raise ValueError('No DEX in APK')
  classes=[c for n in dex for c in dex_classes(z.read(n))]
 hits={g:[c for c in classes if any(c.startswith(p) for p in ps)] for g,ps in PREFIXES.items()}
 bad={g:v for g,v in hits.items() if v}
 if bad:raise ValueError('Feature implementations remain '+json.dumps(bad))
 return {'apk':str(apk),'dex_files':len(dex),'class_count':len(classes),'excluded_java_groups':list(PREFIXES),'native_and_runtime_verified':False}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('apk',type=Path);p.add_argument('--report',type=Path,required=True);a=p.parse_args();report=audit(a.apk);a.report.write_text(json.dumps(report,indent=2)+'\n');print('SANDIUM_DEX_EXCLUSIONS=PASS')
