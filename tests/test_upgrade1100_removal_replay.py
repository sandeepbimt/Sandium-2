import hashlib,importlib.util,json,runpy,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/'tests/fixtures/upgrade1100/removals'
PIN='bd6d26d1bced03c17a98baa86d2cd3425d543d1b'
class RemovalReplay(unittest.TestCase):
 def test_exact_fixture_identity(self):
  evidence=json.loads((FIXTURE.parent/'removal-provenance.json').read_text());self.assertEqual(evidence['brave_sha'],PIN)
  for name,entry in evidence['files'].items():
   raw=(FIXTURE/name).read_bytes();self.assertEqual(hashlib.sha256(raw).hexdigest(),entry['sha256'])
   self.assertEqual(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),entry['git_blob'])
 def run_feature_test(self,name):
  def exact_blob(argv,**kwargs):
   self.assertEqual(argv[:3],['git','-C','fixture-repository']);self.assertEqual(argv[3],'show')
   pin,relative=argv[4].split(':',1);self.assertEqual(pin,PIN);return (FIXTURE/relative).read_bytes()
  script=ROOT/'.circleci/features'/name/'test.py'
  with patch.object(sys,'argv',[str(script),'--source','fixture-repository']),patch('subprocess.check_output',side_effect=exact_blob):
   runpy.run_path(str(script),run_name='__main__')
 def test_playlist_real_upstream_contract(self):self.run_feature_test('playlist-removal')
 def test_billing_real_upstream_contract(self):self.run_feature_test('billing-origin-only')
 def test_news_real_upstream_contract(self):self.run_feature_test('news-removal')
 def test_news_switch_preserves_native_tile_reparenting(self):
  operations=json.loads((ROOT/'.circleci/features/news-removal/operations.json').read_text())
  operation=next(x for x in operations if 'public RecyclerView.ViewHolder onCreateViewHolder' in x['anchor'])
  self.assertIn('switch (viewType)',operation['new'])
  for token in ['case TYPE_STATS:','case TYPE_TOP_SITES:','case TYPE_IMAGE_CREDIT:','existingParent.removeView(mMvTilesContainerLayout)','throw new IllegalArgumentException']:
   self.assertIn(token,operation['new'])
  for token in ['TYPE_NEWS','TYPE_NEW_CONTENT','NewsViewHolder','NewContentViewHolder']:self.assertNotIn(token,operation['new'])
if __name__=='__main__':unittest.main()
