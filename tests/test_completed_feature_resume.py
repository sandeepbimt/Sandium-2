import ast,copy,os,types,unittest
from pathlib import Path
from unittest.mock import Mock,patch

# Isolate pure admission/proof functions from CI import-time environment.
source=Path(__file__).resolve().parents[1]/'tools/completed_feature_resume.py'
module=ast.parse(source.read_text())
selected=ast.Module(body=[n for n in module.body if isinstance(n,ast.FunctionDef) and n.name in ('exact','binding','validate_proof')],type_ignores=[])
class CompletedAdmission(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'RAWS_NATIVE_RESUME_RECEIPT_ID':'a'*64,'RAWS_NATIVE_RESUME_CACHE_KEY':'raws-native-progress-v1-old-4','CIRCLE_SHA1':'b'*40,'CIRCLE_WORKFLOW_ID':'new','RAWS_PIPELINE_NUMBER':'20','CIRCLE_BUILD_NUM':'100'})
        self.env.start();self.addCleanup(self.env.stop)
        import re
        self.valid=Mock(side_effect=lambda r:r['payload'])
        self.ns={'os':os,'re':re,'c':types.SimpleNamespace(D=types.SimpleNamespace(valid=self.valid,c=types.SimpleNamespace(scope=lambda:'scope'))),'fingerprint':lambda:'recipe'}
        exec(compile(selected,str(source),'exec'),self.ns)
        self.receipt={'id':'a'*64,'payload':dict(source='b'*40,scope='scope',workflow='old',pipeline=19,stage=4,apk_verified=True,apk_sha256='c'*64)}
        self.proof=dict(self.ns['binding'](self.receipt),job='100',apk_verified=True,apk=dict(apk_sha256='c'*64,apk_verified=True,apk_signature_verified=True,apk_zip_verified=True))
    def test_old_receipt_is_not_rewritten(self):
        original=copy.deepcopy(self.receipt)
        self.ns['validate_proof'](self.proof,self.receipt,True)
        self.assertEqual(self.receipt,original)
        self.assertEqual(self.receipt['payload']['workflow'],'old')
        self.assertEqual(self.proof['workflow'],'new')
        self.valid.assert_called()
    def test_requires_fresh_other_job_for_pack(self):
        with self.assertRaises(ValueError):self.ns['validate_proof'](self.proof,self.receipt,False)
        with patch.dict(os.environ,CIRCLE_BUILD_NUM='101'):
            self.ns['validate_proof'](self.proof,self.receipt,False)
            with self.assertRaises(ValueError):self.ns['validate_proof'](self.proof,self.receipt,True)
    def test_rejects_wrong_receipt_scope_source_future_or_incomplete(self):
        for key,value in [('scope','oldrecipe'),('source','d'*40),('pipeline',21),('apk_verified',False),('apk_sha256','invalid'),('stage',0)]:
            r=copy.deepcopy(self.receipt);r['payload'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.ns['exact'](r)
        r=copy.deepcopy(self.receipt);r['id']='e'*64
        with self.assertRaises(ValueError):self.ns['exact'](r)
    def test_rejects_wrong_proof_or_missing_actual_apk_checks(self):
        for key,value in [('receipt','d'*64),('workflow','old'),('pipeline',19),('fingerprint','oldrecipe'),('apk_verified',False)]:
            proof=copy.deepcopy(self.proof);proof[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.ns['validate_proof'](proof,self.receipt,True)
        for key in ('apk_sha256','apk_signature_verified','apk_zip_verified'):
            proof=copy.deepcopy(self.proof);proof['apk'].pop(key)
            with self.subTest(key=key),self.assertRaises(ValueError):self.ns['validate_proof'](proof,self.receipt,True)
    def test_transport_selector_not_shell_or_prefix(self):
        for key in ('raws-native-progress-v1-','raws-native-progress-v1-a;curl','raws-native-progress-v1-a b','raws-full-head-v1-a'):
            with patch.dict(os.environ,RAWS_NATIVE_RESUME_CACHE_KEY=key),self.assertRaises(ValueError):self.ns['exact'](self.receipt)
if __name__=='__main__':unittest.main()
