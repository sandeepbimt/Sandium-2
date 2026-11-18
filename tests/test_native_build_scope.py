from pathlib import Path
from unittest.mock import patch
import os,sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import raw
class Scope(unittest.TestCase):
    def test_explicit_feature_branch_flag_and_recipe(self):
        for branch,flag,features,ok in [('raw-sandium/official158','',(),True),('raw-sandium/official158','true',('menu',),False),('raw-sandium/native-ui158','true',('menu','toolbar'),True),('raw-sandium/native-ui158','',('menu',),False),('raw-sandium/native-ui158','true',(),False),('other','true',('menu',),False)]:
            with self.subTest(branch=branch,flag=flag,features=features),patch.dict(os.environ,{'CIRCLE_BRANCH':branch,'RAWS_NATIVE_FEATURE_BUILD':flag}),patch('native_features.load_manifest',return_value=features):
                if ok:raw.require_build_scope()
                else:
                    with self.assertRaises(ValueError):raw.require_build_scope()
if __name__=='__main__':unittest.main()
