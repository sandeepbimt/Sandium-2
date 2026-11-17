import importlib.util,shutil,tempfile,unittest
from pathlib import Path
from build_config import ROOT
spec=importlib.util.spec_from_file_location('x64shards',ROOT/'.circleci/x64-test/sandium-checkpoint-shards.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
class Roundtrip(unittest.TestCase):
 def test_x64_only_handoff_preserves_objects(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);work=root/'brave-work';src=work/'src';out=src/'out/android_Release';arm=src/'out/android_Release_arm64'
   for p in [work/'.sandium',src/'.git',src/'brave/.git',out/'obj',arm/'obj']:p.mkdir(parents=True)
   for p,t in [(work/'.gclient','solutions=[]'),(src/'.git/HEAD','fixture'),(src/'brave/.git/HEAD','fixture'),(out/'build.ninja','fixture'),(out/'args.gn','target_cpu="x64"'),(out/'obj/a.o','x64-object'),(arm/'obj/a.o','arm-object'),(work/'.sandium/checkpoint-manifest.txt','TARGET=android-x64\nCHECKPOINT_VALID=true\n')]:p.write_text(t)
   mod.archive(root,2)
   shutil.rmtree(work)
   mod.restore(root,2)
   self.assertEqual((out/'obj/a.o').read_text(),'x64-object')
   self.assertFalse(arm.exists())
   self.assertIn('TARGET=android-x64',(work/'.sandium/checkpoint-manifest.txt').read_text())
if __name__=='__main__':unittest.main()
