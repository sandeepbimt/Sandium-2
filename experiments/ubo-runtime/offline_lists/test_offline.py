import importlib.util,json,re,subprocess,tempfile,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('offline',HERE/'apply.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Offline(unittest.TestCase):
 def test_lock(self):
  d=m.verify();self.assertEqual(len(d['subscriptions']),30);self.assertEqual(len(d['files']),20)
  self.assertEqual(sum(x.get('unavailable',False) for x in d['subscriptions']),2)
  self.assertEqual(sum(bool(x['upstream_local']) for x in d['subscriptions']),8)
 def test_composed_apply_reset(self):
  with tempfile.TemporaryDirectory() as td:
   src=Path(td);core=src/'brave';core.mkdir();patch=(HERE.parent/'brave-android-extensions.patch').read_bytes()
   names=set(x.decode() for x in re.findall(rb'^\+\+\+ b/(.+)$',patch,re.M))|set(m.loader.INPUTS)|{'common/extensions/api/api_sources.gni','common/extensions/api/_api_features.json','browser/extensions/api/BUILD.gn'}
   for name in names:
    r=subprocess.run(['git','-C','/workspace/scratch/40acbbeff193/brave-core-audit','show','44a84b1f:'+name],capture_output=True)
    if r.returncode==0:
     p=core/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(r.stdout)
   subprocess.run(['git','apply','--whitespace=nowarn','-'],input=patch,cwd=core,check=True,capture_output=True)
   p=src/m.loader.NATIVE;p.parent.mkdir(parents=True);p.write_bytes(Path('/tmp/ubo-loader-pinned/chrome_component_extension_resource_manager.cc').read_bytes())
   subprocess.run(['git','apply','--whitespace=nowarn','-'],input=(core/'patches/chrome-browser-extensions-chrome_component_extension_resource_manager.cc.patch').read_bytes(),cwd=src,check=True,capture_output=True)
   m.loader.apply(src,Path('/tmp/ubo-prepared-1764.zip'));bridge=m.load('bridge',HERE.parent/'shields_bridge/apply.py');bridge.apply(core)
   before={str(p.relative_to(core)):p.read_bytes() for p in core.rglob('*') if p.is_file()}
   m.apply(core);m.apply(core)
   component=core/'components/sandium_ubo';self.assertEqual((component/'disk_resources.h').read_text(),m.loader.build_disk_inventory(core))
   assets=(component/'sandium_ubo/js/assets.js').read_text()
   self.assertLess(assets.index('const details = await assetCacheRead(assetKey, updateReadTime);'),assets.index('const contentURLs = withSandiumOfflineSource('))
   self.assertIn('if ( reIsExternalPath.test(contentURL) && options.dontCache !== true )',assets)
   self.assertEqual(assets.count('const contentURLs = withSandiumOfflineSource('),1)
   self.assertNotIn('seedOfflineLists',(component/'sandium_ubo/js/sandium-lists.js').read_text())
   self.assertEqual(len(list((component/'sandium_ubo/assets/sandium-offline').glob('*.txt'))),20)
   f=component/'sandium_ubo/js/sandium-offline-lists.js';original=f.read_bytes();f.write_bytes(original+b'\nunknown')
   with self.assertRaisesRegex(ValueError,'Unowned edit'):m.reset(core)
   f.write_bytes(original);m.reset(core);m.reset(core)
   self.assertEqual(before,{str(p.relative_to(core)):p.read_bytes() for p in core.rglob('*') if p.is_file()})
   bridge.reset(core);m.loader.reset(src)
if __name__=='__main__':unittest.main()
