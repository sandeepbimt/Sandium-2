import sys,tempfile,subprocess,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'.circleci/full-u'))
import recipe
class Recipe(unittest.TestCase):
 def test_compile_policy_changes_scope(self):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t);subprocess.run(['git','init','-q',t],check=True);(r/'.circleci').mkdir();p=r/'.circleci/gn-policy';p.write_text('PGO0 ThinLTO true component false arm64')
   subprocess.run(['git','add','.circleci'],cwd=r,check=True);before=recipe.fingerprint(r)
   p.write_text('PGO1 ThinLTO true component false arm64');self.assertNotEqual(before,recipe.fingerprint(r))
   (r/'android').mkdir();asset=r/'android/welcome.xml';asset.write_text('old UI');subprocess.run(['git','add','android'],cwd=r,check=True)
   prior=recipe.fingerprint(r);asset.write_text('new UI');self.assertNotEqual(prior,recipe.fingerprint(r))
if __name__=='__main__':unittest.main()
