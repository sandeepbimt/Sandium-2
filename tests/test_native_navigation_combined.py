"""Engine + status trace/inset composition and exact rollback; no native compile."""
import gzip,importlib.util,json,tempfile,unittest
from pathlib import Path
from native_navigation_test_support import seed_settings, SETTINGS
ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
nav=load('nav_combined',ROOT/'experiments/native-navigation/apply.py')
scroll=load('scroll_combined',ROOT/'.circleci/scripts/apply-sandium-scroll-status-bar.py')
trace=load('trace_combined',ROOT/'.circleci/scripts/trace-sandium-back-geometry.py')
class Combined(unittest.TestCase):
 def test_all_on_off_trace_reset_and_exact_frozen_restore(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)
   data=json.loads(gzip.decompress((ROOT/'tests/fixtures/native-navigation.json.gz').read_bytes()))
   for p,s in data['frozen'].items():
    f=root/p;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(s)
   seed_settings(root)
   for name,p in scroll.FILES.items():
    s=scroll.transform(name,(ROOT/'.circleci/tests/fixtures/status-bar'/name).read_text())
    if p==trace.PATH:s=trace.transform(s)
    f=root/p;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(s)
   before={p:p.read_text() for p in root.rglob('*') if p.is_file()}
   nav.execute(root,True);nav.execute(root,True,True)
   controller=(root/trace.PATH).read_text()
   self.assertNotIn('shouldSandiumUnderlap',controller);self.assertNotIn('SandiumUnderlapReapply',controller)
   self.assertNotIn('SANDIUM_STATUS_SPACER',(root/scroll.FILES['TopControlsStacker.java']).read_text())
   for path,pairs in SETTINGS.items():
    self.assertEqual((root/path).read_text(),'\n'.join(before for before,after in pairs))
   for p in nav.geometry_changes(root):
    self.assertNotIn('mSandiumTopProtectionHeight',p.read_text())
   nav.execute(root,False);nav.execute(root,False,True)
   self.assertEqual(before,{p:p.read_text() for p in before})
if __name__=='__main__':unittest.main()
