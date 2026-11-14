import importlib.util,json,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('e',ROOT/'.circleci/scripts/removal-evidence.py');e=importlib.util.module_from_spec(spec);spec.loader.exec_module(e)
class Evidence(unittest.TestCase):
 def fixture(self):
  t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);r=Path(t.name)
  (r/'brave-apk').mkdir();(r/'.circleci/features').mkdir(parents=True)
  (r/'.circleci/features/removal-recipe.json').write_text('{}')
  for name in e.REPORTS:(r/'brave-apk'/name).write_text('{"status":"PASS"}')
  (r/'apk').write_bytes(b'apk')
  (r/'brave-apk/removal-dex.json').write_text(json.dumps({'schema':2,'result':'listed_class_definitions_absent','apk_sha256':e.digest(r/'apk'),'recipe_binding':{'sha256':e.digest(r/'.circleci/features/removal-recipe.json')}}))
  return r
 def test_bound_source_recipe_and_artifact(self):
  r=self.fixture();e.capture(r,'new');result=e.bind(r,'new',r/'apk')
  self.assertEqual(result['apk_sha256'],e.digest(r/'apk'));self.assertFalse(result['device_verified'])
 def test_reject_stale_source_recipe_or_reports(self):
  for scenario in ('source','recipe','report','missing','apk','dex'):
   r=self.fixture();e.capture(r,'new')
   if scenario=='recipe':(r/'.circleci/features/removal-recipe.json').write_text('{"changed":true}')
   if scenario=='report':(r/'brave-apk/removal-native.json').write_text('{"status":"FAIL"}')
   if scenario=='apk':(r/'apk').write_bytes(b'other')
   if scenario=='dex':(r/'brave-apk/removal-dex.json').write_text('{}')
   if scenario=='missing':(r/'brave-apk/removal-leo.json').unlink()
   with self.assertRaises((ValueError,FileNotFoundError)):e.bind(r,'old' if scenario=='source' else 'new',r/'apk')
 def test_failed_graph_cannot_capture(self):
  r=self.fixture();(r/'brave-apk/removal-native.json').write_text('{"status":"FAIL"}')
  with self.assertRaises(ValueError):e.capture(r,'new')
if __name__=='__main__':unittest.main()
