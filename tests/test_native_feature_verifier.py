"""Verifier boundary tests; actual feature postimages tested by composition suites."""
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import raw

class FeatureVerifier(unittest.TestCase):
    def invoke(self, names, *, preparation=False, feature_error=None):
        with tempfile.TemporaryDirectory() as directory:
            src=Path(directory)
            (src/'chrome').mkdir()
            (src/'chrome/VERSION').write_text('MAJOR=158\nMINOR=0\nBUILD=8127\nPATCH=42\n')
            data={'chromium':{'revision':'a'*40,'version':'158.0.8127.42'}}
            plan=SimpleNamespace(tracked_paths=frozenset({'chrome/approved.java'}))
            with patch.object(raw,'run',side_effect=[SimpleNamespace(stdout='a'*40+'\n'),SimpleNamespace(stdout='\0'.join(names))]), \
                 patch('native_features.plan',return_value=plan) as pre, \
                 patch('native_features.verify_applied',return_value=plan,side_effect=feature_error) as final:
                raw.verify(src,data,allow_feature_preimages=preparation)
                self.assertEqual(pre.call_count, int(preparation))
                self.assertEqual(final.call_count, int(not preparation))

    def test_exact_feature_paths_do_not_relax_other_changes(self):
        self.invoke(['chrome/approved.java'])
        with self.assertRaisesRegex(ValueError,'Unapproved tracked'):
            self.invoke(['chrome/approved.java','chrome/foreign.java'])

    def test_partial_feature_is_only_admitted_during_preparation(self):
        self.invoke([],preparation=True)
        with self.assertRaisesRegex(ValueError,'Missing feature'):
            self.invoke([],feature_error=ValueError('Missing feature'))

if __name__=='__main__':unittest.main()
