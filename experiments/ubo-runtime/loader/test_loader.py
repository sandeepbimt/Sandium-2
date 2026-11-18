import importlib.util,json,hashlib,re,subprocess,tempfile,unittest,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('loader_apply',HERE/'apply.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
CORE=Path('/workspace/scratch/40acbbeff193/brave-core-audit')
RAW=Path('/tmp/ubo-loader-pinned/chrome_component_extension_resource_manager.cc')
BUNDLE=Path('/tmp/ubo-prepared-1764.zip')
class Tests(unittest.TestCase):
 def test_fixed_identity(self):
  import base64
  i=json.loads((HERE/'identity.json').read_text());h=hashlib.sha256(base64.b64decode(i['public_key'])).hexdigest()[:32]
  self.assertEqual(i['extension_id'],''.join(chr(ord('a')+int(c,16)) for c in h))
 def test_full_pinned_port_loader_replay_and_resource_inventory(self):
  if not BUNDLE.exists() or not RAW.exists():self.skipTest('exact full release and native input required')
  patch=(HERE.parent/'brave-android-extensions.patch').read_bytes()
  names=re.findall(rb'^\+\+\+ b/(.+)$',patch,re.M)
  with tempfile.TemporaryDirectory() as td:
   src=Path(td);core=src/'brave';core.mkdir()
   for n in set(x.decode() for x in names)|{'resources/resource_ids.spec','brave_paks.gni','common/extensions/api/api_sources.gni','common/extensions/api/_api_features.json','browser/extensions/api/BUILD.gn'}:
    r=subprocess.run(['git','-C',str(CORE),'show','44a84b1f:'+n],capture_output=True)
    if r.returncode==0:
     p=core/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(r.stdout)
   subprocess.run(['git','apply','--whitespace=nowarn','-'],input=patch,cwd=core,check=True,capture_output=True)
   n='chrome/browser/extensions/chrome_component_extension_resource_manager.cc';p=src/n;p.parent.mkdir(parents=True);p.write_bytes(RAW.read_bytes())
   subprocess.run(['git','apply','--whitespace=nowarn','-'],input=(core/'patches/chrome-browser-extensions-chrome_component_extension_resource_manager.cc.patch').read_bytes(),cwd=src,check=True,capture_output=True)
   baseline={str(p.relative_to(src)):p.read_bytes() for p in src.rglob('*') if p.is_file()}
   m.apply(src,BUNDLE)
   first={str(p.relative_to(src)):hashlib.sha256(p.read_bytes()).hexdigest() for p in src.rglob('*') if p.is_file()}
   m.apply(src,BUNDLE)
   second={str(p.relative_to(src)):hashlib.sha256(p.read_bytes()).hexdigest() for p in src.rglob('*') if p.is_file()}
   self.assertEqual(first,second)
   # Full installed-bundle composition must unwind in reverse order. Testing
   # each receipt separately does not establish that their overlapping files
   # (factory, resources, and start.js) can survive a continuation checkpoint.
   bridge_spec=importlib.util.spec_from_file_location('composed_bridge',HERE.parent/'shields_bridge/apply.py')
   bridge=importlib.util.module_from_spec(bridge_spec);bridge_spec.loader.exec_module(bridge)
   bridge.apply(core)
   self.assertTrue((core/bridge.RECEIPT).exists())
   with self.assertRaisesRegex(ValueError,'Unowned modification'):m.reset(src)
   bridge.reset(core)
   after_bridge_reset={str(p.relative_to(src)):hashlib.sha256(p.read_bytes()).hexdigest() for p in src.rglob('*') if p.is_file()}
   self.assertEqual(first,after_bridge_reset)
   manifest=json.loads((core/'components/sandium_ubo/sandium_ubo/manifest.json').read_text())
   self.assertEqual(manifest['version'],'1.76.4');self.assertEqual(manifest['manifest_version'],2)
   self.assertEqual(len(list((core/'components/sandium_ubo/sandium_ubo').rglob('*')))>668,True)
   grd=(core/'components/sandium_ubo/resources.grd').read_text();mapping=(core/'components/sandium_ubo/resource_map.h').read_text()
   self.assertEqual(grd.count('<include '),668);self.assertEqual(mapping.count('{"sandium_ubo/'),668)
   import xml.etree.ElementTree as ET
   header=ET.fromstring(grd).find("./outputs/output[@type='rc_header']")
   self.assertIsNotNone(header.find("emit[@emit_type='prepend']"))
   mgr=(core/'chromium_src/chrome/browser/extensions/chrome_component_extension_resource_manager.cc').read_text()
   guard=mgr.index('#if BUILDFLAG(IS_ANDROID)')
   self.assertLess(mgr.index('#include "build/build_config.h"'),guard)
   self.assertLess(mgr.index('#include "extensions/buildflags/buildflags.h"'),guard)
   # Execute the actual pinned GRIT header formatter using an XML-node adapter.
   # Not a replacement formatter or full GN/GRIT build.
   formatter=__import__('runpy').run_path(str(HERE/'fixtures/rc_header.py'))
   class Node:
    def __init__(self,e):self.e=e;self.name=e.tag;self.attrs=e.attrib;self.children=[Node(c) for c in e]
    def GetType(self):return self.attrs['type']
    def GetCdata(self):return self.e.text or ''
   class Root:
    def GetOutputFiles(self):return [Node(header)]
    def IsAllowlistSupportEnabled(self):return False
    def GetIdMap(self):return {}
    def ActiveDescendants(self):return []
   generated=''.join(formatter['Format'](Root()))
   self.assertNotIn('atlres.h',generated)
   h=src/'grit-header-test.h';h.write_text(generated)
   cpp=src/'grit-header-test.cc';cpp.write_text('#include "grit-header-test.h"\nint main(){return 0;}\n')
   subprocess.run(['g++','-std=c++20','-Wall','-Werror',str(cpp),'-o',str(src/'grit-header-test')],check=True)
   cpp.unlink();h.unlink();(src/'grit-header-test').unlink()

   component=core/'components/sandium_ubo'
   inventory=(component/'disk_resources.h').read_text()
   self.assertEqual(inventory,m.build_disk_inventory(core))
   for name,symbol,digest in re.findall(r'\{"([^"\n]+)", (IDR_SANDIUM_UBO_[A-Z0-9_]+), "([0-9a-f]{64})"\}',inventory):
    self.assertEqual(hashlib.sha256((component/'sandium_ubo'/name).read_bytes()).hexdigest(),digest)
   self.assertEqual(inventory.count('    {"'),668)
   factory=(core/'chromium_src/chrome/browser/extensions/component_loader_factory.cc').read_text()
   self.assertIn('PostTaskAndReplyWithResult',factory)
   self.assertIn('weak_factory_.InvalidateWeakPtrs()',factory)
   self.assertIn('Add(std::move(component->manifest), component->directory)',factory)
   self.assertIn('// SANDIUM_UBO_PROFILE_INITIALIZATION',factory)
   native=(component/'materializer.cc').read_text()
   self.assertIn('extension_l10n_util::LocalizeExtension(',native)
   self.assertIn('ValidateDirectory(directory, assets)',native)
   self.assertIn('base::FileEnumerator::SHOW_SYM_LINKS',native)
   self.assertIn('base::PathExists(directory) ||',native)

   self.assertIn('BASE_FEATURE(kSandiumUboRuntime, base::FEATURE_DISABLED_BY_DEFAULT)',(core/'browser/brave_browser_features.cc').read_text())
   self.assertNotIn('return AreAndroidExtensionsAllowed() ||',(core/'browser/extensions/android/brave_extension_management.cc').read_text())
   receipt=json.loads((src/m.STATE/'receipt.json').read_text())
   owned=core/'brave_paks.gni';saved=owned.read_bytes();owned.write_bytes(saved+b'\nUNOWNED\n')
   with self.assertRaisesRegex(ValueError,'Unowned modification'):m.reset(src)
   self.assertTrue((src/m.STATE/'receipt.json').exists());owned.write_bytes(saved)
   # Simulate interruption mid-reset, then resume reset safely.
   real=m.atomic_write;count=[0]
   def interrupted(p,data):
    count[0]+=1
    if count[0]==3:raise RuntimeError('simulated power loss')
    real(p,data)
   m.atomic_write=interrupted
   try:
    with self.assertRaises(RuntimeError):m.reset(src)
   finally:m.atomic_write=real
   m.reset(src);m.reset(src)
   restored={str(p.relative_to(src)):p.read_bytes() for p in src.rglob('*') if p.is_file() and m.STATE not in p.parts}
   self.assertEqual(baseline,restored)
   # Apply interruption after durable planning receipt; replay restores full overlay.
   def interrupted_apply(src_,receipt_,key):
    entries=list(receipt_['files'].items())
    name,e=entries[0];real(src_/name,(src_/m.STATE/'blobs'/e['after']).read_bytes())
    raise RuntimeError('interrupted apply')
   original_transition=m.transition;m.transition=interrupted_apply
   try:
    with self.assertRaises(RuntimeError):m.apply(src,BUNDLE)
   finally:m.transition=original_transition
   m.apply(src,BUNDLE)
   actual={str(p.relative_to(src)):hashlib.sha256(p.read_bytes()).hexdigest() for p in src.rglob('*') if p.is_file() and m.STATE not in p.parts}
   expected={k:v for k,v in first.items() if not k.startswith(m.STATE+'/')}
   self.assertEqual(actual,expected)
   m.reset(src)
 def test_final_bridge_reindex_is_pure_and_tracks_changed_assets(self):
  with tempfile.TemporaryDirectory() as td:
   core=Path(td)
   m.materialize(core,BUNDLE)
   component=core/'components/sandium_ubo'
   before=(component/'disk_resources.h').read_text()
   script=component/'sandium_ubo/js/start.js';script.write_bytes(script.read_bytes()+b'\n// Reviewed bridge hook\n')
   after=m.build_disk_inventory(core)
   self.assertNotEqual(before,after)
   self.assertEqual((component/'disk_resources.h').read_text(),before)
   self.assertIn(hashlib.sha256(script.read_bytes()).hexdigest(),after)
   script.unlink();script.symlink_to('/tmp/unowned')
   with self.assertRaisesRegex(ValueError,'Missing disk resource'):
    m.build_disk_inventory(core)

if __name__=='__main__':unittest.main()
