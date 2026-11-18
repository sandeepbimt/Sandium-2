from pathlib import Path
from unittest.mock import patch
import json,os,sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import ci_final_archive as a
class Stage(unittest.TestCase):
    def test_stage_specific_progress(self):
        with tempfile.TemporaryDirectory() as d,patch.object(a,'ROOT',Path(d)),patch.object(a,'fingerprint',return_value='new'),patch.dict(os.environ,{'RAWS_FINAL_PACK_ONLY':'false'}):
            for stage in (1,2,3,4,5):
                p=Path(d)/f'handoff/stage{stage}/state.json';p.parent.mkdir(parents=True);p.write_text(json.dumps({'fingerprint':'new','stage':stage}))
                with patch.dict(os.environ,{'RAWS_STAGE':str(stage)}):self.assertEqual(a.state()['stage'],stage)
            with patch.dict(os.environ,{'RAWS_STAGE':'6'}),self.assertRaises(ValueError):a.state()
if __name__=='__main__':unittest.main()
