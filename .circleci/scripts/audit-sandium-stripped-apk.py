#!/usr/bin/env python3
"""Inspect actual DEX class definitions, not incidental string references.
This checks listed class names in DEX, not obfuscated-name equivalence, runtime/network
behavior or native absence. Native dependency closure is a separate mandatory gate.
"""
import argparse,hashlib,json,re,struct,zipfile
from pathlib import Path
PREFIXES={
 'vpn':['Lorg/chromium/chrome/browser/vpn/','Lcom/wireguard/'],
 'wallet':['Lorg/chromium/chrome/browser/crypto_wallet/'],
 'playlist':['Lorg/chromium/chrome/browser/playlist/'],
 'leo':['Lorg/chromium/chrome/browser/ai_chat/','Lorg/chromium/chrome/browser/leo/','Lorg/chromium/chrome/browser/brave_leo/','Lorg/chromium/chrome/browser/settings/BraveLeo','Lorg/chromium/chrome/browser/toolbar/adaptive/BraveLeo','Lorg/chromium/chrome/browser/omnibox/BraveLeo','Lorg/chromium/chrome/browser/omnibox/suggestions/BraveLeo'],
 'news':['Lorg/chromium/chrome/browser/brave_news/','Lorg/chromium/chrome/browser/settings/BraveNews'],
 'rewards_ads':['Lorg/chromium/chrome/browser/rewards/','Lorg/chromium/chrome/browser/ads/','Lorg/chromium/chrome/browser/ntp/SponsoredRichMediaWebView','Lorg/chromium/chrome/browser/ntp/BraveNewTabTakeoverInfobar','Lorg/chromium/chrome/browser/ntp/NewTabTakeoverSafeAreaReporter'],
}
REQUIRED_ACTIVITIES = (
 'org.chromium.chrome.browser.firstrun.WelcomeOnboardingActivity',
 'org.chromium.chrome.browser.settings.BraveSettingsActivity',
 'org.chromium.chrome.browser.customtabs.BraveAccountCustomTabActivity',
 'org.chromium.chrome.browser.customtabs.FullScreenCustomTabActivity',
)
UNPROVEN_GROUPS = ["Email aliases", "Speedreader", "Talk", "Tor", "Wayback Machine",
                   "Web Discovery", "Reporting: daily ping, crash uploads, P3A"]
def sha256(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()

def u32(d,n):
 if n<0 or n+4>len(d):raise ValueError('DEX integer outside file')
 return struct.unpack_from('<I',d,n)[0]

def dex_classes(d):
 if len(d)<112 or not re.fullmatch(rb'dex\n0(?:35|37|38|39|40)\x00',d[:8]):
  raise ValueError('Invalid or unsupported DEX format')
 if u32(d,32)!=len(d):raise ValueError('Truncated DEX')
 if u32(d,36)!=112 or u32(d,40)!=0x12345678:raise ValueError('Unsupported DEX header/endian')
 strings_n,strings=struct.unpack_from('<II',d,56)
 types_n,types=struct.unpack_from('<II',d,64)
 classes_n,classes=struct.unpack_from('<II',d,96)
 for count,offset,width in [(strings_n,strings,4),(types_n,types,4),(classes_n,classes,32)]:
  if count and (offset<112 or offset%4 or offset+count*width>len(d)):
   raise ValueError('DEX table outside file')
 def text(index):
  if index>=strings_n:raise ValueError('Invalid string index')
  at=u32(d,strings+4*index)
  if at<112 or at>=len(d):raise ValueError('Invalid string offset')
  for i in range(5):
   if at>=len(d):raise ValueError('Truncated ULEB128')
   b=d[at];at+=1
   if i==4 and b>15:raise ValueError('Invalid ULEB128')
   if b<128:break
  else:raise ValueError('Invalid ULEB128')
  end=d.find(b'\0',at)
  if end<0:raise ValueError('Unterminated DEX string')
  try:return d[at:end].decode('utf-8','surrogatepass')
  except UnicodeDecodeError as e:raise ValueError('Invalid DEX string encoding') from e
 result=[]
 for n in range(classes_n):
  t=u32(d,classes+32*n)
  if t>=types_n:raise ValueError('Invalid class type')
  name=text(u32(d,types+4*t))
  if not name.startswith('L') or not name.endswith(';'):raise ValueError('Invalid class descriptor')
  result.append(name)
 if len(result)!=len(set(result)):raise ValueError('Duplicate DEX class definition')
 return result

def mapping_names(path):
 """Map only R8/ProGuard class lines; members/comments are not class definitions."""
 names={}
 for line in Path(path).read_text().splitlines():
  match=re.fullmatch(r'([^\s]+) -> ([^\s]+):',line)
  if not match:continue
  original,encoded=match.groups()
  descriptor='L'+encoded.replace('.','/')+';'
  if descriptor in names:raise ValueError('Ambiguous mapping class '+encoded)
  names[descriptor]='L'+original.replace('.','/')+';'
 if not names:raise ValueError('No class mappings in supplied mapping')
 return names

def audit(apk,recipe=None,mapping=None):
 before=sha256(apk)
 with zipfile.ZipFile(apk) as z:
  names=z.namelist()
  if len(names)!=len(set(names)):raise ValueError('Duplicate APK archive entry')
  forbidden=[n for n in names if n in ('assets/brave_vpn_confirm.json',
   'assets/ntp_news_optin_icon_animation.json') or re.fullmatch(r'lib/[^/]+/libwg-go\.so',n)]
  if forbidden:raise ValueError('Excluded packaged payload remains '+json.dumps(forbidden))
  if recipe and 'AndroidManifest.xml' not in names:
   raise ValueError('Required AndroidManifest.xml missing from APK')
  if 'AndroidManifest.xml' in names:
   manifest=z.read('AndroidManifest.xml')
   for token in ('com.wireguard.android.backend.GoBackend$VpnService','android.permission.BIND_VPN_SERVICE'):
    if token.encode() in manifest or token.encode('utf-16le') in manifest:
     raise ValueError('Excluded VPN manifest reference remains '+token)
   # Manifest-bound activity names are retained by Android/R8. A missing
   # onboarding declaration caused #1162 to finish immediately on first launch.
   for activity in REQUIRED_ACTIVITIES:
    if activity.encode() not in manifest and activity.encode('utf-16le') not in manifest:
     raise ValueError('Required retained activity missing from APK manifest '+activity)
  dex=[n for n in names if n.endswith('.dex')]
  if not dex:raise ValueError('No DEX in APK')
  classes=[c for n in dex for c in dex_classes(z.read(n))]
 if not classes:raise ValueError('No DEX class definitions')
 if len(classes)!=len(set(classes)):raise ValueError('Duplicate multidex class definition')
 checked=set(classes)
 if mapping:
  translated=mapping_names(mapping)
  checked.update(translated[c] for c in classes if c in translated)
 hits={g:[c for c in sorted(checked) if any(c.startswith(p) for p in ps)] for g,ps in PREFIXES.items()}
 bad={g:v for g,v in hits.items() if v}
 if bad:raise ValueError('Feature implementations remain '+json.dumps(bad))
 if before!=sha256(apk):raise ValueError('APK changed during audit')
 report={'schema':2,'apk':str(apk),'apk_sha256':before,'apk_bytes':Path(apk).stat().st_size,
  'packaged_payload_checks':['VPN asset','News opt-in asset','WireGuard native library','VPN manifest references'],
  'dex_files':len(dex),'class_count':len(classes),
  'result':'listed_class_definitions_absent','checked_java_prefix_groups':list(PREFIXES),
  'groups_without_java_prefix_proof':UNPROVEN_GROUPS,
  'mapping_checked':bool(mapping),'mapping_sha256':sha256(mapping) if mapping else None,
  'all_13_removed_verified':False,'native_and_runtime_verified':False,
  'limitations':['Prefix absence is not whole-component absence.',
   'R8 mapping, if supplied, is checked only against class definitions in this APK; mapping provenance needs the build gate.',
   'Generated GN/link closure, resources, manifest/services, local and remote reporting, runtime and upgrade behavior require separate evidence.']}
 if recipe:
  data=json.loads(Path(recipe).read_text())
  groups=data.get('groups',[])
  if data.get('schema')!=1 or len(groups)!=13 or len(set(groups))!=13:
   raise ValueError('Expected unique canonical 13-group recipe')
  if not all(re.fullmatch(r'[0-9a-f]{40}',data.get(k,'')) for k in ('brave_pin','chromium_pin')):
   raise ValueError('Recipe upstream pin missing/invalid')
  report['recipe_binding']={'sha256':sha256(recipe),'groups':groups,
   'brave_pin':data['brave_pin'],'chromium_pin':data['chromium_pin'],
   'graph_verified':False}
 return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('apk',type=Path);p.add_argument('--report',type=Path,required=True)
 p.add_argument('--recipe',type=Path);p.add_argument('--mapping',type=Path)
 a=p.parse_args()
 # An unsuccessful retry must not leave an old success report at this output path.
 a.report.unlink(missing_ok=True)
 report=audit(a.apk,a.recipe,a.mapping)
 a.report.write_text(json.dumps(report,indent=2)+'\n')
 print('SANDIUM_DEX_EXCLUSIONS=PASS scope=listed_class_definitions_only all13_verified=false')
