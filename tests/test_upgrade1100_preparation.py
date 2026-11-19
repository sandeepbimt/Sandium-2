import hashlib, importlib.util, json, shutil, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/'tests/fixtures/upgrade1100'
def module(name,file):
 spec=importlib.util.spec_from_file_location(name,ROOT/'.circleci/scripts'/file)
 result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result
profile=module('upgrade1100_profile','upgrade_source_profile.py')
overlay=module('upgrade1100_full','apply-sandium-full-overlays.py')
class Preparation(unittest.TestCase):
 def test_exact_profile_and_package(self):
  self.assertTrue(profile.load()['ready'])
  with tempfile.TemporaryDirectory() as directory:
   core=Path(directory);shutil.copyfile(ROOT/'docs/upgrades/1.100.58/upstream-package.json',core/'package.json')
   with patch.object(profile.subprocess,'check_output',side_effect=[profile.BRAVE_SHA,profile.CHROMIUM_SHA]):
    result=profile.verify(core,core/'src');self.assertFalse(result['source_sync_verified']);self.assertFalse(result['apk_verified'])
   with patch.object(profile.subprocess,'check_output',return_value='44a84b1f89d9a35287289d6a3d493e362f5a5123'):
    with self.assertRaisesRegex(ValueError,'pin'):profile.verify(core,core/'src')
   (core/'package.json').write_text('{}')
   with patch.object(profile.subprocess,'check_output',side_effect=[profile.BRAVE_SHA,profile.CHROMIUM_SHA]):
    with self.assertRaisesRegex(ValueError,'package'):profile.verify(core,core/'src')
 def test_all_live_full_overlay_operations_on_exact_upstream(self):
  provenance=json.loads((FIXTURE/'provenance.json').read_text())
  for name,digest in provenance['files'].items():self.assertEqual(hashlib.sha256((FIXTURE/'core'/name).read_bytes()).hexdigest(),digest)
  with tempfile.TemporaryDirectory() as directory:
   src=Path(directory);core=src/'brave';shutil.copytree(FIXTURE/'core',core)
   with patch.object(overlay,'git_sha',side_effect=lambda p:profile.BRAVE_SHA if p==core else profile.CHROMIUM_SHA),patch.object(sys,'argv',['overlay','--core',str(core),'--src',str(src)]):
    overlay.main();first={p.relative_to(core):p.read_bytes() for p in core.rglob('*') if p.is_file()}
    overlay.main();self.assertEqual(first,{p.relative_to(core):p.read_bytes() for p in core.rglob('*') if p.is_file()})
   self.assertIn('return false;', (core/'components/playlist/core/browser/utils.cc').read_text())
   self.assertIn('SANDIUM_ORIGIN_ENTRY_REMOVED',(core/'android/java/brave-res/xml/brave_main_preferences.xml').read_text())
 def test_full_overlay_rejects_old_pin_before_writing(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory)
   with patch.object(overlay,'git_sha',return_value='44a84b1f89d9a35287289d6a3d493e362f5a5123'),patch.object(sys,'argv',['overlay','--core',str(root),'--src',str(root)]):
    with self.assertRaisesRegex(RuntimeError,'pin mismatch'):overlay.main()
   self.assertEqual(list(root.iterdir()),[])
if __name__=='__main__':unittest.main()
