"""Exact Chromium158 opaque status policy; no Android/device validation claim."""
import gzip,hashlib,importlib.util,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('opaque158',ROOT/'.circleci/scripts/opaque-status-paint.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Opaque158(unittest.TestCase):
 def test_exact_sources_preserve_task_background_and_replay(self):
  fixture=json.loads(gzip.decompress((ROOT/'tests/fixtures/opaque-status158.json.gz').read_bytes()))
  self.assertEqual(fixture['pin'],'52bdd21723d5db0c9ab11716d38feac74828cf84')
  for path,item in fixture['files'].items():
   s=item['text'];d=s.encode();self.assertEqual(hashlib.sha1(b'blob '+str(len(d)).encode()+b'\0'+d).hexdigest(),item['git_blob'])
   out=m.transform(path,s)
   self.assertEqual(out,m.transform(path,out))
   if path.endswith('StatusBarColorController.java'):
    self.assertIn('/* forceLightIconColor= */ false,\n                backgroundColor);',out)
    self.assertIn('new TaskDescriptionColors(opaqueColor, taskDescriptionBackgroundColor)',out)
    self.assertIn('mCurrentTab.getBackgroundColor()',out)
    self.assertIn('public void onBackgroundColorChanged(Tab tab, @ColorInt int color)',out)
    altered=s.replace('                backgroundColor);','                unreviewedBackground);')
    with self.assertRaises(RuntimeError):m.transform(path,altered)
    altered=out.replace('color = EdgeToEdgeSystemBarColorHelper.getSandiumOpaqueStatusColor(color);','color = 0;')
    with self.assertRaises(RuntimeError):m.transform(path,altered)
if __name__=='__main__':unittest.main()
