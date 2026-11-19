import gzip,hashlib,json,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class CompleteTargetInputs(unittest.TestCase):
 def test_all_native_and_bridge_fixture_paths_have_real_reset_owners(self):
  recipe=json.loads((ROOT/'.circleci/features/removal-recipe.json').read_text())
  owned=set(recipe['chromium_restore'])|{'brave/'+p for p in recipe['core_restore']}
  required=set(json.loads(gzip.decompress((ROOT/'tests/fixtures/native-navigation.json.gz').read_bytes()))['frozen'])
  for name in ('native-holder','native-handoff-adapter','static-layout-eligibility','content-registration','java-handoff-registration','capture-coordinates','compositor-view-java','root-ui-handoff-gate'):
   evidence=json.loads(gzip.decompress((ROOT/'experiments/single-handoff/fixtures'/(name+'.json.gz')).read_bytes()))
   required.update(evidence['files'] if 'files' in evidence else [evidence['path']])
  self.assertFalse(required-owned,sorted(required-owned))
 def test_ui_links_actual_target_fixture_and_full_existing_contract(self):
  proof=json.loads((ROOT/'tests/fixtures/upgrade1100/reset-provenance.json').read_text())['files']
  data=json.loads(gzip.decompress((ROOT/'tests/fixtures/upgrade1100/ui-links-core.json.gz').read_bytes()))
  with tempfile.TemporaryDirectory() as temporary:
   src=Path(temporary);core=src/'brave'
   for p,text in data.items():
    raw=text.encode();self.assertEqual(hashlib.sha256(raw).hexdigest(),proof['core/'+p]['sha256'])
    target=core/p;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
   import runpy
   relative=runpy.run_path(str(ROOT/'.circleci/scripts/apply-sandium-ui-links.py'))['CONNECTION']
   raw=(ROOT/'tests/fixtures/upgrade1100/ConnectionInfoView.java').read_bytes();self.assertEqual(hashlib.sha256(raw).hexdigest(),proof['chromium/'+relative]['sha256'])
   target=src/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
   subprocess.run(['python3',str(ROOT/'.circleci/scripts/test-sandium-ui-links.py'),'--core',str(core),'--src',str(src),'--source-profile','target158'],check=True,capture_output=True)
if __name__=='__main__':unittest.main()
