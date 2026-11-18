import copy,os,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import ci_feature_seed as m
import ci_full as c
class Resume(unittest.TestCase):
    def test_explicit_same_recipe_identity(self):
        receipt={'id':'a'*64,'payload':{'source':'commit','stage':3,'apk_verified':False}}
        env={'CIRCLE_SHA1':'commit','RAWS_NATIVE_RESUME_RECEIPT_ID':'a'*64,'RAWS_NATIVE_RESUME_CACHE_KEY':'raws-native-progress-v1-exact'}
        with patch.dict(os.environ,env),patch.object(c.D,'valid',side_effect=lambda r:r['payload']):
            self.assertEqual(m.exact_resume(receipt),receipt['payload'])
            for field,bad in [('source','foreign'),('stage',6),('apk_verified',None)]:
                altered=copy.deepcopy(receipt);altered['payload'][field]=bad
                with self.assertRaises(ValueError):m.exact_resume(altered)
            for key,value in [('RAWS_NATIVE_RESUME_RECEIPT_ID','b'*64),('RAWS_NATIVE_RESUME_CACHE_KEY','broad-prefix'),('RAWS_NATIVE_RESUME_CACHE_KEY','raws-native-progress-v1-\n')]:
                with patch.dict(os.environ,{key:value}),self.assertRaises(ValueError):m.exact_resume(receipt)
    def test_expiry_or_scope_failure_not_ignored(self):
        with patch.dict(os.environ,{'RAWS_NATIVE_RESUME_RECEIPT_ID':'a'*64,'RAWS_NATIVE_RESUME_CACHE_KEY':'raws-native-progress-v1-exact'}),patch.object(c.D,'valid',side_effect=ValueError('expired')):
            with self.assertRaisesRegex(ValueError,'expired'):m.exact_resume({'id':'a'*64})
if __name__=='__main__':unittest.main()
