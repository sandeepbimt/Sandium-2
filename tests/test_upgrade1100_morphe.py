import subprocess,shutil
import gzip,hashlib,importlib.util,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
ROOT=Path(__file__).resolve().parents[1]
def load(path,name):
 spec=importlib.util.spec_from_file_location(name,ROOT/path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
M=load('.circleci/scripts/apply-sandium-fast-morphe.py','upgrade_morphe')
P=load('.circleci/upgrades/product.py','upgrade_product')
DATA=json.loads(gzip.decompress((ROOT/'tests/fixtures/upgrade1100/morphe.json.gz').read_bytes()))
class Morphe(unittest.TestCase):
 def test_exact_replay_idempotence_and_blob_identity(self):
  with tempfile.TemporaryDirectory() as temporary:
   src=Path(temporary);core=src/'brave'
   for v in DATA.values():
    raw=v['before'].encode();self.assertEqual(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),v['git_blob'])
    p=(core if v['kind']=='core' else src)/v['path'];p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
   with patch.object(M,'sha',side_effect=lambda p:M.BRAVE_SHA if p==core else M.CHROMIUM_SHA),patch.object(sys,'argv',['morphe',str(src)]):
    for _ in range(2):
     M.main()
     for v in DATA.values():self.assertEqual(((core if v['kind']=='core' else src)/v['path']).read_text(),v['after'])
 def test_wrong_pin_before_any_edit(self):
  with patch.object(M,'sha',return_value='wrong'),patch.object(M,'replace_once') as replace,patch.object(sys,'argv',['morphe','/unused']):
   with self.assertRaisesRegex(RuntimeError,'pin mismatch'):M.main()
   replace.assert_not_called()
 def test_base_rejects_wrong_source_before_retained_check(self):
  source=Mock();source.verify.side_effect=ValueError('Wrong source')
  with patch.object(P,'source_module',return_value=source),patch.object(P.importlib.util,'spec_from_file_location') as legacy:
   with self.assertRaisesRegex(ValueError,'Wrong source'):P.verify_base(ROOT)
   legacy.assert_not_called()
 def test_startup_reset_owned_and_intermediate_does_not_undo_it(self):
  recipe=json.loads((ROOT/'.circleci/features/removal-recipe.json').read_text());self.assertEqual(recipe['chromium_restore'].count(DATA['partner']['path']),1)
  import inspect
  body=inspect.getsource(P.verify_base);self.assertNotIn('restore_paths(',body);self.assertNotIn('clean_gn_args(',body)
  self.assertIn(hashlib.sha256(DATA['partner']['after'].encode()).hexdigest(),body)
 def test_intermediate_integrity_retains_startup_and_rejects_drift(self):
  with tempfile.TemporaryDirectory() as temporary:
   root=Path(temporary);src=root/'brave-work/src';core=src/'brave';core.mkdir(parents=True)
   for relative in ('android/BUILD.gn','android/java/org/chromium/chrome/browser/toolbar/top/BraveToolbarLayoutImpl.java'):
    target=core/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/'tests/fixtures/upgrade1100/removals'/relative,target)
   retained=core/'browser/brave_wallet/retained.cc';retained.parent.mkdir(parents=True);retained.write_text('retained upstream fixture\n')
   subprocess.run(['git','init','-q',str(core)],check=True)
   subprocess.run(['git','-C',str(core),'add','.'],check=True)
   subprocess.run(['git','-C',str(core),'-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-qm','fixture'],check=True)
   partner=src/DATA['partner']['path'];partner.parent.mkdir(parents=True);partner.write_text(DATA['partner']['after'])
   args=src/'out/android_Release_arm64/args.gn';args.parent.mkdir(parents=True);args.write_text('enable_ai_chat=false\n')
   with patch.object(P,'source_module',return_value=Mock()):
    result=P.verify_base(root);self.assertFalse(result['build_ready']);self.assertEqual(partner.read_text(),DATA['partner']['after']);self.assertEqual(args.read_text(),'enable_ai_chat=false\n')
    partner.write_text(DATA['partner']['before'])
    with self.assertRaisesRegex(ValueError,'startup postimage'):P.verify_base(root)
    partner.write_text(DATA['partner']['after']);retained.write_text('unexpected change\n')
    with self.assertRaisesRegex(SystemExit,'modified='):P.verify_base(root)
if __name__=='__main__':unittest.main()
