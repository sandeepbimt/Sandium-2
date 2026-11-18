"""Regression boundaries for prepared promotion; subprocess validation is mocked.

These tests exercise receipt ownership admission, not GN or service execution.
"""
import copy
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import ci_feature_seed as m
import ci_full as c

class PreparedPromotionIdentity(unittest.TestCase):
    def test_promotion_rechecks_prepared_receipt_ownership(self):
        env={'CIRCLE_WORKFLOW_ID':'current-workflow','CIRCLE_BUILD_NUM':'22',
             'CIRCLE_SHA1':'new-source','RAWS_PIPELINE_NUMBER':'30','RAWS_STAGE':'1'}
        baseline={'scope':c.D.c.COMPAT,'compatibility':c.D.c.COMPAT,
                  'workflow':'current-workflow','source':'new-source','pipeline':30,'stage':1,
                  'apk_verified':False,'plan':{'layers':[]}}
        faults={'workflow':'older-workflow','source':'older-source','pipeline':29,'stage':2,
                'apk_verified':True,'plan':{'layers':[{'id':'unexpected-layer'}]}}
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ,env):
            root=Path(directory)
            for key,value in faults.items():
                with self.subTest(field=key):
                    payload=copy.deepcopy(baseline);payload[key]=value
                    receipt={'id':'reviewed-digest','payload':payload}
                    # A stale restore can carry a valid same-scope receipt. A
                    # current-job proof must NOT launder its older ownership.
                    proof={'receipt':receipt['id'],'scope':payload['scope'],
                           'workflow':env['CIRCLE_WORKFLOW_ID'],'job':env['CIRCLE_BUILD_NUM'],
                           'apk_verified':False}
                    def read(path):
                        return receipt if Path(path).name=='selected.json' else proof
                    with patch.object(m,'ROOT',root), patch.object(c.D,'HEAD',root/'head.json'), \
                         patch.object(c.D,'verify_restored'),patch.object(c.D,'valid',return_value=payload), \
                         patch.object(c.D.c,'read',side_effect=read),patch.object(c.D.c,'save') as save:
                        with self.assertRaises(ValueError):
                            m.promote_prepared()
                        save.assert_not_called()

if __name__=='__main__':unittest.main()
