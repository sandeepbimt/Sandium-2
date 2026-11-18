import json, os, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import ci_compile
class Admission(unittest.TestCase):
    def test_only_current_fresh_bootstrap_admits_preimages(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);state=root/'.checkpoint-state';state.mkdir()
            with patch.object(ci_compile,'ROOT',root), patch.object(ci_compile,'fingerprint',return_value='recipe'), patch.dict(os.environ,{'CIRCLE_WORKFLOW_ID':'current'}):
                self.assertFalse(ci_compile.fresh_feature_preparation())
                marker=state/'fresh.json'
                marker.write_text(json.dumps({'scope':'raws-full-v1-recipe','workflow':'current'}))
                self.assertTrue(ci_compile.fresh_feature_preparation())
                with self.assertRaises(ValueError):ci_compile.fresh_feature_preparation(2)
                for name in ('selected.json','restored-proof.json'):
                    (state/name).write_text('{}')
                    with self.assertRaises(ValueError):ci_compile.fresh_feature_preparation()
                    (state/name).unlink()
                marker.write_text(json.dumps({'scope':'raws-full-v1-old','workflow':'current'}))
                with self.assertRaises(ValueError):ci_compile.fresh_feature_preparation()
if __name__=='__main__':unittest.main()
