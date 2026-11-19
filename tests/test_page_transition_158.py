import gzip,hashlib,importlib.util,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
 s=importlib.util.spec_from_file_location(name,ROOT/path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
b=load('base','.circleci/scripts/apply-sandium-blur-transition.py')
f=load('full','.circleci/scripts/apply-sandium-page-transition-full.py')
n=load('native','experiments/single-handoff/native_blur.py')
DATA=json.loads(gzip.decompress((ROOT/'tests/fixtures/upgrades158/page-transition.json.gz').read_bytes()))
class PageTransition158(unittest.TestCase):
 def source(self,path):
  item=DATA[str(path)];s=item['text'];self.assertEqual(hashlib.sha256(s.encode()).hexdigest(),item['sha256']);return s
 def test_actual_base_then_full_java_resources(self):
  for key,bfn,ffn in [('APPEARANCE_XML',b.transform_appearance_xml,f.transform_appearance_xml),('APPEARANCE_JAVA',b.transform_appearance_java,f.transform_appearance_java),('APPEARANCE_TEST',b.transform_appearance_test,f.transform_appearance_test),('STRINGS_GRD',b.transform_grd,f.transform_grd)]:
   with self.subTest(key=key):
    s=self.source('brave/'+str(getattr(b,key)));a=bfn(s);self.assertEqual(bfn(a),a);v=ffn(a);self.assertEqual(ffn(v),v)
    if key=='APPEARANCE_JAVA':
     final=n.settings(v);self.assertEqual(n.settings(final),final)
  for key,fn in [('ANDROID_BUILD_GN',f.transform_android_build_gn),('MAIN_PREFERENCES_JAVA',f.transform_main_preferences)]:
   s=self.source('brave/'+str(getattr(f,key)));v=fn(s);self.assertEqual(fn(v),v)
  s=self.source(str(b.ROOT_TARGET));v=f.transform_startup(b.transform_chromium_startup(s));self.assertEqual(f.transform_startup(v),v)
 def test_actual_native158_intermediate_overlay(self):
  for path,fn in [(f.TRANSITION_CC,f.transform_transition_cc),(f.TRANSITION_H,f.transform_transition_h),(f.FEATURES_CC,f.transform_features_cc),(f.FEATURES_H,f.transform_features_h)]:
   s=n.fixture(str(path));out=fn(s);self.assertEqual(fn(out),out)
if __name__=='__main__':unittest.main()
