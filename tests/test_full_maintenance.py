import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'.circleci/bridge'))
import json
import os
import tempfile
import time
import unittest
from unittest import mock
import bridge
import full_driver as f
from test_bridge_rollup import clone

class MaintenanceTests(unittest.TestCase):
    def test_refresh_preserves_source_apk_and_replays_current_state(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);state=root/'state';state.mkdir();layers=root/'layers';layers.mkdir()
            raw=b'{"shards": []}';(root/f.d.MANIFEST).write_bytes(raw);baseid=bridge.base_id(raw)
            base=root/'original';base.mkdir();(base/'keep').write_text('original')
            work=root/'work';clone(base,work);before=bridge.begin(work,baseid,'job')
            (work/'keep').write_text('new');r=bridge.capture(work,before,'job',layers/'0.zip',lambda:None)
            plan=dict(base=dict(id=baseid,manifest_sha256=bridge.digest(raw),key='old-base',expires_at=time.time()+100,archive_bytes=0),head=r['id'],layers=[dict(id=r['id'],parent=baseid,key='old-layer',expires_at=time.time()+100,content_bytes=(layers/'0.zip').stat().st_size)])
            payload=dict(plan=plan,source='SOURCE_UNCHANGED',apk_verified=True,pipeline=1,workflow='old',stage=5)
            receipt=dict(id='OLD_RECEIPT',payload=payload);f.d.c.save(state/'selected.json',receipt)
            with mock.patch.multiple(f.d,ROOT=root,STATE=state,LAYERS=layers,INCOMING=root/'incoming',operation_budget=1000,create=True), mock.patch.object(f.d,'gate'), mock.patch.object(f.d,'valid',side_effect=lambda rec:rec['payload']),mock.patch.object(f.d,'new_key',side_effect=lambda k,i:k+'-'+i),mock.patch.object(f.cli,'run_bounded',side_effect=lambda *a:clone(base,root/'brave-work')),mock.patch.dict(os.environ,{'SANDIUM_PIPELINE_NUMBER':'2','CIRCLE_WORKFLOW_ID':'new','SANDIUM_STAGE':'0'}):
                f.maintenance_capture()
                with self.assertRaises(FileNotFoundError):f.publish()
                import shutil
                saved=root/'saved';saved.mkdir()
                shutil.copy2(root/f.d.MANIFEST,saved/'manifest')
                shutil.copytree(root/'incoming',saved/'incoming')
                f.maintenance_clear_saved_local()
                self.assertFalse((root/'incoming').exists())
                self.assertTrue((root/'brave-work/keep').exists())
                with self.assertRaises(FileNotFoundError):f.maintenance_readback()
                shutil.copy2(saved/'manifest',root/f.d.MANIFEST)
                shutil.copytree(saved/'incoming',root/'incoming')
                with mock.patch.object(f.cli,'run_bounded'):
                    f.maintenance_readback()
                proof=json.loads((state/'maintenance-readback-proof.json').read_text())
                self.assertEqual(proof['candidate'],json.loads((state/'candidate.json').read_text())['id'])
                with (root/'incoming/payload.zip').open('ab') as stream:stream.write(b'bad')
                with mock.patch.object(f.cli,'run_bounded'):
                    with self.assertRaisesRegex(ValueError,'digest mismatch'):f.maintenance_readback()
            candidate=json.loads((state/'candidate.json').read_text())['payload']
            self.assertEqual(candidate['source'],'SOURCE_UNCHANGED');self.assertTrue(candidate['apk_verified'])
            self.assertEqual(candidate['previous_receipt'],'OLD_RECEIPT');self.assertEqual(candidate['stage'],0)
            self.assertEqual((root/'brave-work/keep').read_text(),'new')
            self.assertEqual(len(candidate['plan']['layers']),1)
            self.assertGreater(candidate['plan']['base']['expires_at'],time.time()+13*86400)
    def test_optional_job_requires_exact_workflow_apk_and_request(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);state=root/'state';state.mkdir();head=root/'receipt'
            payload=dict(source='sha',workflow='workflow',pipeline=3,stage=1,apk_verified=True,
                plan=dict(base=dict(key='base',archive_bytes=0,expires_at=time.time()+14*86400),layers=[]))
            f.d.c.save(head,dict(id='receipt',payload=payload))
            f.d.c.save(state/'job-start.json',dict(epoch=time.time()-100))
            with mock.patch.multiple(f.d,STATE=state,HEAD=head),mock.patch.object(f.d,'gate'),mock.patch.object(f.d,'valid',side_effect=lambda rec:rec['payload']),mock.patch.object(f.d.c,'disk_guard'),mock.patch.object(f.d.c,'halt') as halt,mock.patch.object(f.d.c,'scope',return_value='scope'),mock.patch.dict(os.environ,{'CIRCLE_SHA1':'sha','CIRCLE_WORKFLOW_ID':'workflow','SANDIUM_PIPELINE_NUMBER':'3','SANDIUM_STAGE':'1'}):
                f.post_publish_eligibility()
                f.optional_check();halt.assert_not_called()
                self.assertEqual(json.loads((state/'selected.json').read_text())['id'],'receipt')
                payload['workflow']='other';f.d.c.save(head,dict(id='wrong',payload=payload))
                f.optional_check();halt.assert_called_once()
            self.assertEqual(json.loads((state/'selected.json').read_text())['id'],'receipt')

    def test_due_reserves_five_stages(self):
        plan=dict(base=dict(expires_at=time.time()+14*86400),layers=[dict(expires_at=time.time()+14*86400)]*11)
        self.assertTrue(f.summary(plan,'r')['capacity_due'])
        plan['layers']=plan['layers'][:10];self.assertFalse(f.summary(plan,'r')['capacity_due'])
        plan['base']['expires_at']=time.time()+86400;self.assertTrue(f.summary(plan,'r')['refresh_due'])
if __name__=='__main__':unittest.main()
