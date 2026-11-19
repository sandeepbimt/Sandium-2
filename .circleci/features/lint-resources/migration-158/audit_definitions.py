from pathlib import Path
import subprocess,json,collections,concurrent.futures,hashlib,xml.etree.ElementTree as ET,re
import argparse
parser=argparse.ArgumentParser(description='Read-only target158 definition audit; generates evidence, never approvals')
parser.add_argument('--core', required=True, type=Path)
args=parser.parse_args()
repo=Path(__file__).resolve().parents[4]; core=args.core
if subprocess.check_output(['git','-C',str(core),'rev-parse','HEAD'],text=True).strip() != 'bd6d26d1bced03c17a98baa86d2cd3425d543d1b':
 raise ValueError('Wrong source pin')
data=repo/'.circleci/features/lint-resources';out=data/'migration-158'
pin='bd6d26d1bced03c17a98baa86d2cd3425d543d1b'
tree={l.split('\t')[1]:l.split()[2] for l in subprocess.check_output(['git','-C',str(core),'ls-tree','-r',pin],text=True).splitlines()}
old=json.loads((data/'inventory.json').read_text());supp=json.loads((data/'inventory-1401.json').read_text());candidates=[]
for r in old['resources']:
 if r['approved']: candidates.append((r['resource'],r.get('upstream_definition')))
for r in supp['resources']:candidates.append((r['resource'],r['definition']))
paths={d['path'] for r,d in candidates if d and d['path'] in tree};texts={}
def fetch(p):
 raw=subprocess.check_output(['git','-C',str(core),'show',pin+':'+p],timeout=90)
 if hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()!=tree[p]:raise ValueError('Blob identity mismatch')
 return p,raw
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
 for p,b in ex.map(fetch,sorted(paths)):texts[p]=b
report=[]
for rid,d in candidates:
 row={'resource':rid,'old_approval_carried':False,'target_exception_approved':False}
 if not d:row['definition_status']='owned_resource_requires_new_composition'
 elif d['path'] not in tree:row.update(definition_status='upstream_file_absent',path=d['path'])
 else:
  p=d['path'];b=texts[p];text=b.decode(errors='replace');name=rid.split('.')[-1];typ=rid.split('.')[1];present=False
  if p.endswith(('.grd','.grdp')):present=bool(re.search(r'<message\s+name="IDS_'+re.escape(name.upper())+'"',text))
  elif p.endswith('.gni'):present='"'+name+'.xml"' in text
  elif p.endswith('.xml'):
   root=ET.fromstring(text)
   present=name in {n.attrib.get('name','').replace('.','_') for n in root} if root.tag=='resources' else Path(p).stem==name
  else:present=Path(p).stem==name
  row.update(path=p,target_git_blob=tree[p],target_sha256=hashlib.sha256(b).hexdigest(),definition_status='present' if present else 'declaration_absent',whole_definition_file_unchanged=tree[p]==d.get('git_blob'))
 report.append(row)
result={'target_brave_pin':pin,'target_chromium_pin':'52bdd21723d5db0c9ab11716d38feac74828cf84','scope':'Definition comparison only. No final target composition or158 lint execution; all964 previous approvals remain NOT carried forward.','counts':dict(collections.Counter(r['definition_status'] for r in report)),'resources':report}
(out/'definition-comparison.json').write_text(json.dumps(result,indent=2)+'\n'); print(result['counts']);print('unchanged_files_rows',sum(r.get('whole_definition_file_unchanged',False) for r in report))
for p in ['chromium_src/chrome/android/expectations/lint-suppressions.xml','chromium_src/build/android/gyp/lint.py']:
 b=fetch(p)[1];(out/Path(p).name).write_bytes(b);print(p,tree[p],hashlib.sha256(b).hexdigest())
