import importlib, json, os, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import feature_seed_checkpoint as m
class Checkpoint(unittest.TestCase):
    def test_admission_is_inputs_only_and_explicit(self):
        from baseline_seed import RECEIPT,BASELINE_FINGERPRINT
        record={'status':'feature-inputs-ready','baseline_receipt':RECEIPT,'baseline_fingerprint':BASELINE_FINGERPRINT,'feature_fingerprint':'new','apk_verified':False,'checkpoint_accepted':False}
        with patch.object(m.c.D.c,'read',return_value=record),patch.object(m,'fingerprint',return_value='new'),patch.object(m,'verify'),patch.object(m,'lock',return_value={}),patch('native_features.load_manifest',return_value=('menu','toolbar')):
            self.assertEqual(m.admission(),record)
            for key,value in [('status','failed'),('apk_verified',True),('checkpoint_accepted',True),('feature_fingerprint','old')]:
                altered=dict(record);altered[key]=value
                with patch.object(m.c.D.c,'read',return_value=altered),self.assertRaises(ValueError):m.admission()
            with patch('native_features.load_manifest',return_value=()),self.assertRaises(ValueError):m.admission()
    def test_capture_preserves_archive_reserve(self):
        with patch.object(m.c.D.c,'read',return_value={'epoch':1000}),patch.object(m.time,'time',return_value=2800):
            with self.assertRaises(ValueError):m.budget(minimum=1620,reserve=840)
        with patch.object(m.c.D.c,'read',return_value={'epoch':1000}),patch.object(m.time,'time',return_value=2600):
            self.assertEqual(m.budget(minimum=1620,reserve=840),860)
    def test_no_normal_head_or_completion_publication(self):
        source=Path(m.__file__).read_text()
        self.assertNotIn('c.D.HEAD.write',source)
        self.assertNotIn("save(c.D.HEAD",source)
        self.assertIn("save(STATE/'receipt.json',candidate)",source)
if __name__=='__main__':unittest.main()
