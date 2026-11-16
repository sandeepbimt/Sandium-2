import importlib.util,tempfile,unittest,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('s',ROOT/'.circleci/scripts/sync-sandium-removal-overlays.py');s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
class Sync(unittest.TestCase):
 def fixture(self):
  t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);root=Path(t.name);core=root/'brave';core.mkdir()
  paths=list(s.MAPPINGS)+sorted(s.UI_OWNED_COPIED)
  for p in paths:
   f=core/p;f.parent.mkdir(parents=True,exist_ok=True);f.write_text('<resources>gold</resources>')
  return root,core,{'core_restore':paths,'ui_only_core_restore':sorted(s.UI_OWNED_COPIED)}
 def test_new_ui_palette_and_ntp_both_published(self):
  root,core,m=self.fixture();s.apply(core,root,m)
  for p in s.UI_OWNED_COPIED:self.assertEqual((root/p.replace('android/java/res/','chrome/android/java/res/',1)).read_bytes(),(core/p).read_bytes())
 def test_production_manifest_publishes_developer_hint_and_replays(self):
  # Unlike the synthetic fixture, load the real inventory so newly registered
  # copied resources cannot silently escape this guard's allowlist.
  root,core,_=self.fixture()
  manifest=json.loads((ROOT/'.circleci/features/removal-recipe.json').read_text())
  relative='android/java/res/xml/developer_preferences.xml'
  source=core/relative;source.parent.mkdir(parents=True,exist_ok=True)
  source.write_bytes((ROOT/'tests/fixtures/about-branding/developer_preferences.xml').read_bytes())
  brand_spec=importlib.util.spec_from_file_location('branding',ROOT/'.circleci/scripts/apply-sandium-visible-branding.py')
  branding=importlib.util.module_from_spec(brand_spec);brand_spec.loader.exec_module(branding)
  source.write_text(branding.rebrand_developer_hint(source.read_text()))
  dest=root/'chrome'/relative;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text('stale copy')
  unrelated=dest.parent/'unrelated.xml';unrelated.write_text('keep UI changes')
  for _ in range(2):
   s.apply(core,root,manifest)
   self.assertEqual(source.read_bytes(),dest.read_bytes())
   self.assertIn('About Sandium',dest.read_text())
   self.assertIn('Copyright',dest.read_text())
   self.assertEqual(unrelated.read_text(),'keep UI changes')
  # Every explicitly allowed UI source is covered by today's real inventory.
  copied={p for p in manifest['core_restore'] if p.startswith(s.COPIED_ROOTS)}
  self.assertEqual(copied & set(manifest['ui_only_core_restore']),s.UI_OWNED_COPIED)
 def test_unknown_ui_exception_rejected(self):
  root,core,m=self.fixture();p='android/java/res/layout/unknown.xml';m['core_restore'].append(p);m['ui_only_core_restore'].append(p)
  with self.assertRaises(ValueError):s.apply(core,root,m)
 def test_new_removal_copied_input_requires_mapping(self):
  root,core,m=self.fixture();m['core_restore'].append('android/java/res/layout/other.xml')
  with self.assertRaises(ValueError):s.apply(core,root,m)
if __name__=='__main__':unittest.main()
