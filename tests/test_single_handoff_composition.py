import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('handoff_comp',ROOT/'experiments/single-handoff/composition.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)

class Composition(unittest.TestCase):
    def test_outer_restored_before_native_replay(self):
        calls=[]
        with tempfile.TemporaryDirectory() as d, patch.object(m.handoff,'execute',side_effect=lambda r,e,**k:calls.append(('outer',e))), patch.object(m.native,'execute',side_effect=lambda r,e,**k:calls.append(('native',e))), patch.object(m,'verify_combined'):
            m.execute(Path(d),True,True)
        self.assertEqual(calls,[('outer',False),('native',True),('outer',True)])
    def test_disabled_outer_is_restored_too(self):
        calls=[]
        with tempfile.TemporaryDirectory() as d, patch.object(m.handoff,'execute',side_effect=lambda r,e,**k:calls.append(('outer',e))), patch.object(m.native,'execute',side_effect=lambda r,e,**k:calls.append(('native',e))):
            m.execute(Path(d),False,False)
        self.assertEqual(calls,[('outer',False),('native',False)])
    def test_no_partial_config(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(RuntimeError,'requires native'): m.execute(Path(d),False,True)
    def setup_source(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);r=Path(t.name)
        p=r/'source.java';p.write_text('native')
        entry={'before':'product','after':'native','before_sha256':m.native.sha('product'),'after_sha256':m.native.sha('native')}
        (r/m.native.STATE).write_text(json.dumps({'schema':1,'recipe_sha256':m.native.recipe_hash(),'files':{'source.java':entry}}))
        with patch.object(m.handoff,'proposed',return_value={p:'candidate'}):m.handoff.execute(r,True)
        return r,p
    def test_combined_verify_without_mutation_and_restore(self):
        r,p=self.setup_source();m.verify_combined(r);self.assertEqual(p.read_text(),'candidate')
        m.handoff.execute(r,False);self.assertEqual(p.read_text(),'native')
        m.native.execute(r,False);self.assertEqual(p.read_text(),'product')
    def test_native_postimage_drift_rejected(self):
        r,p=self.setup_source();state=json.loads((r/m.native.STATE).read_text());entry=state['files']['source.java'];entry['after']='other';entry['after_sha256']=m.native.sha('other');(r/m.native.STATE).write_text(json.dumps(state))
        with self.assertRaisesRegex(RuntimeError,'not based on native'):m.verify_combined(r)
        self.assertEqual(p.read_text(),'candidate')
    def test_disabled_verify_rejects_remaining_outer(self):
        r,p=self.setup_source()
        with self.assertRaisesRegex(RuntimeError,'remains applied'):m.execute(r,True,False,True)

if __name__=='__main__':unittest.main()
