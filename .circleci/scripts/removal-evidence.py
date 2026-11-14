#!/usr/bin/env python3
"""Bind current generated-graph evidence to one source, recipe and APK.
Static verification is not device/network verification or absence of all strings.
"""
import argparse,hashlib,json,os
from pathlib import Path
REPORTS=('removal-native.json','removal-low-six.json','removal-leo.json')
def digest(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
def capture(root,source):
 if not source:raise ValueError('Current source revision required')
 root=Path(root);reports=root/'brave-apk';recipe=root/'.circleci/features/removal-recipe.json'
 hashes={}
 for name in REPORTS:
  p=reports/name
  if json.loads(p.read_text()).get('status')!='PASS':raise ValueError('Graph report not passed: '+name)
  hashes[name]=digest(p)
 payload={'schema':1,'source_revision':source,'recipe_sha256':digest(recipe),'reports':hashes}
 (reports/'removal-graph-receipt.json').write_text(json.dumps(payload,indent=2)+'\n')
 return payload
def bind(root,source,apk):
 root=Path(root);reports=root/'brave-apk';receipt=json.loads((reports/'removal-graph-receipt.json').read_text())
 if receipt.get('schema')!=1 or receipt.get('source_revision')!=source or not source:raise ValueError('Stale graph source')
 if receipt['recipe_sha256']!=digest(root/'.circleci/features/removal-recipe.json'):raise ValueError('Stale graph recipe')
 if set(receipt['reports'])!=set(REPORTS):raise ValueError('Incomplete graph receipts')
 for name,sha in receipt['reports'].items():
  if digest(reports/name)!=sha or json.loads((reports/name).read_text()).get('status')!='PASS':raise ValueError('Changed graph evidence')
 dex=json.loads((reports/'removal-dex.json').read_text())
 if dex.get('schema')!=2 or dex.get('result')!='listed_class_definitions_absent':raise ValueError('DEX audit not passed')
 if dex.get('apk_sha256')!=digest(apk):raise ValueError('DEX audit belongs to another APK')
 if dex.get('recipe_binding',{}).get('sha256')!=receipt['recipe_sha256']:raise ValueError('DEX audit recipe mismatch')
 # DEX checker independently has fail-closed exit status; report hash binds its
 # declared limited scope rather than pretending it proves all native code absent.
 result=dict(receipt,apk_sha256=digest(apk),apk_size=Path(apk).stat().st_size,dex_report_sha256=digest(reports/'removal-dex.json'),device_verified=False,scope='Current generated graph exclusions plus declared APK static checks; compatibility declarations retained',runtime_network_verified=False)
 (reports/'removal-evidence.json').write_text(json.dumps(result,indent=2)+'\n')
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['capture','bind']);p.add_argument('--root',type=Path,required=True);p.add_argument('--apk',type=Path);a=p.parse_args()
 if a.action=='capture':capture(a.root,os.environ.get('CIRCLE_SHA1',''))
 else:bind(a.root,os.environ.get('CIRCLE_SHA1',''),a.apk)
