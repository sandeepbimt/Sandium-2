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
            def restore_base(*args):
                self.assertFalse((layers/'0.zip').exists())
                self.assertTrue((root/'.full-maintenance.zip').is_file())
                self.assertEqual(f.d.c.read(state/'selected.json'),receipt)
                self.assertFalse((state/'candidate.json').exists())
                clone(base,root/'brave-work')
            with mock.patch.multiple(f.d,ROOT=root,STATE=state,LAYERS=layers,INCOMING=root/'incoming',operation_budget=1000,create=True), mock.patch.object(f.d,'gate'), mock.patch.object(f.d,'valid',side_effect=lambda rec:rec['payload']),mock.patch.object(f.d,'new_key',side_effect=lambda k,i:k+'-'+i),mock.patch.object(f.cli,'run_bounded',side_effect=restore_base),mock.patch.dict(os.environ,{'SANDIUM_PIPELINE_NUMBER':'2','CIRCLE_WORKFLOW_ID':'new','SANDIUM_STAGE':'0'}):
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
    def test_refresh_failure_never_replaces_accepted_head(self):
        for failure in ('existing_workspace', 'corrupt_input', 'base_restore'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as t:
                root=Path(t);state=root/'state';state.mkdir();layers=root/'layers';layers.mkdir()
                raw=b'{"shards": []}';(root/f.d.MANIFEST).write_bytes(raw);baseid=bridge.base_id(raw)
                work=root/'work';work.mkdir();(work/'keep').write_text('original')
                before=bridge.begin(work,baseid,'job');(work/'keep').write_text('updated')
                archive=layers/'0.zip';r=bridge.capture(work,before,'job',archive,lambda:None)
                receipt=dict(id='OLD_RECEIPT',payload=dict(plan=dict(
                    base=dict(id=baseid,manifest_sha256=bridge.digest(raw)),
                    layers=[dict(id=r['id'])])))
                f.d.c.save(state/'selected.json',receipt)
                if failure=='existing_workspace':(root/'brave-work').mkdir()
                if failure=='corrupt_input':
                    with archive.open('ab') as stream:stream.write(b'corrupt')
                input_bytes=archive.read_bytes()
                with mock.patch.multiple(f.d,ROOT=root,STATE=state,LAYERS=layers,operation_budget=1000,create=True), mock.patch.object(f.d,'gate'), mock.patch.object(f.d,'valid',side_effect=lambda rec:rec['payload']), mock.patch.object(f.cli,'run_bounded',side_effect=RuntimeError('extraction failed')) as extract:
                    with self.assertRaises((ValueError,RuntimeError)):f.maintenance_capture()
                self.assertEqual(f.d.c.read(state/'selected.json'),receipt)
                self.assertFalse((state/'candidate.json').exists())
                if failure=='base_restore':
                    extract.assert_called_once()
                    self.assertFalse(archive.exists())
                    self.assertTrue((root/'.full-maintenance.zip').is_file())
                else:
                    extract.assert_not_called()
                    self.assertEqual(archive.read_bytes(),input_bytes)
                    self.assertFalse((root/'.full-maintenance.zip').exists())

    def test_optional_job_requires_exact_workflow_apk_and_request(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);state=root/'state';state.mkdir();head=root/'receipt'
            payload=dict(source='sha',workflow='workflow',pipeline=3,stage=1,apk_verified=True,
                plan=dict(base=dict(key='base',archive_bytes=0,expires_at=time.time()+86400),layers=[]))
            f.d.c.save(head,dict(id='receipt',payload=payload))
            f.d.c.save(state/'job-start.json',dict(epoch=time.time()-100))
            with mock.patch.multiple(f.d,STATE=state,HEAD=head),mock.patch.object(f.d,'gate'),mock.patch.object(f.d,'valid',side_effect=lambda rec:rec['payload']),mock.patch.object(f.d.c,'disk_guard'),mock.patch.object(f.d.c,'halt') as halt,mock.patch.object(f.d.c,'scope',return_value='scope'),mock.patch.dict(os.environ,{'CIRCLE_SHA1':'sha','CIRCLE_WORKFLOW_ID':'workflow','SANDIUM_PIPELINE_NUMBER':'3','SANDIUM_STAGE':'1'}):
                f.post_publish_eligibility()
                f.optional_check();halt.assert_not_called()
                self.assertEqual(json.loads((state/'selected.json').read_text())['id'],'receipt')
                payload['workflow']='other';f.d.c.save(head,dict(id='wrong',payload=payload))
                f.optional_check();halt.assert_called_once()
            self.assertEqual(json.loads((state/'selected.json').read_text())['id'],'receipt')

    def test_increment_publication_preserves_restored_dependency_deadlines(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);state=root/'state';state.mkdir();incoming=root/'incoming'
            now=time.time();plan=dict(base=dict(id='base',key='base-key',expires_at=now+86400),head='old',layers=[dict(id='old',parent='base',key='old-key',expires_at=now+3*86400)])
            f.d.c.save(state/'selected.json',dict(id='restored',payload=dict(plan=plan)))
            f.d.c.save(state/'inventory.json',{})
            def captured(work, inventory, identity, archive, quiesce):
                archive.write_bytes(b'increment');return dict(id='new',parent='old')
            with mock.patch.multiple(f.d,ROOT=root,STATE=state,INCOMING=incoming),mock.patch.object(f.d,'gate'),mock.patch.object(f.d,'valid',side_effect=lambda rec:rec['payload']),mock.patch.object(f.bridge,'capture',side_effect=captured),mock.patch.object(f.d,'new_key',return_value='new-key'),mock.patch.object(f.d,'make_candidate') as candidate,mock.patch.dict(os.environ,{'CIRCLE_WORKFLOW_ID':'workflow','CIRCLE_BUILD_NUM':'1'}):
                f.capture()
            saved,parent=candidate.call_args.args
            self.assertEqual(parent,'restored');self.assertEqual(saved['base'],plan['base'])
            self.assertEqual(saved['layers'][:-1],plan['layers'])
            self.assertGreater(saved['layers'][-1]['expires_at'],now+13*86400)
            self.assertTrue(f.summary(saved,'new')['refresh_due'])

    def test_fresh_head_skips_optional_even_with_stale_eligible_request(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);state=root/'state';state.mkdir();head=root/'receipt'
            payload=dict(source='sha',workflow='workflow',pipeline=3,stage=1,apk_verified=True,
                plan=dict(base=dict(key='base',archive_bytes=0,expires_at=time.time()+14*86400),layers=[]))
            f.d.c.save(head,dict(id='receipt',payload=payload))
            f.d.c.save(state/'job-start.json',dict(epoch=time.time()-100))
            with mock.patch.multiple(f.d,STATE=state,HEAD=head),mock.patch.object(f.d,'gate'),mock.patch.object(f.d,'valid',side_effect=lambda rec:rec['payload']),mock.patch.object(f.d.c,'disk_guard') as disk,mock.patch.object(f.d.c,'halt') as halt,mock.patch.dict(os.environ,{'CIRCLE_SHA1':'sha','CIRCLE_WORKFLOW_ID':'workflow','SANDIUM_PIPELINE_NUMBER':'3','SANDIUM_STAGE':'1'}):
                f.post_publish_eligibility()
                request=f.d.c.read(state/'optional-refresh-request.json')
                self.assertFalse(request['eligible']);self.assertFalse(request['expiry']['refresh_due'])
                request['eligible']=True;f.d.c.save(state/'optional-refresh-request.json',request)
                f.optional_check();halt.assert_called_once();disk.assert_not_called()
                self.assertFalse((state/'selected.json').exists())
                self.assertEqual(f.d.c.read(head)['id'],'receipt')
                payload['plan']['base']['expires_at']=float('nan');f.d.c.save(head,dict(id='bad',payload=payload))
                with self.assertRaises(ValueError):f.post_publish_eligibility()
                with self.assertRaises(ValueError):f.optional_check()
                self.assertFalse((state/'selected.json').exists())

    def test_dependency_age_uses_oldest_layer_not_latest_receipt(self):
        now=2000000000
        plan=dict(base=dict(expires_at=now+14*86400), layers=[dict(expires_at=now+86400),dict(expires_at=now+14*86400)])
        report=f.summary(plan,'new-published-receipt',now=now)
        self.assertTrue(report['refresh_due'])
        self.assertEqual(report['earliest_dependency_expires_at'],f.datetime.datetime.fromtimestamp(now+86400,f.datetime.timezone.utc).isoformat())
        plan['layers']=[]
        self.assertFalse(f.summary(plan,'new-published-receipt',now=now)['refresh_due'])
        for seconds,expected in [(2*86400,True),(2*86400+1,False)]:
            plan['base']['expires_at']=now+seconds
            self.assertEqual(f.summary(plan,'r',now=now)['refresh_due'],expected)

    def test_expiry_metadata_never_guesses_new_ttl(self):
        now=2000000000
        for value in [None,True,'2026-11-29',float('nan'),float('inf'),now,now-1,now+16*86400]:
            with self.subTest(value=value),self.assertRaises(ValueError):
                f.summary(dict(base=dict(expires_at=value),layers=[]),'r',now=now)
        for plan in [{},{'base':{},'layers':[]},{'base':{'expires_at':now+86400},'layers':[{}]}]:
            with self.assertRaises(ValueError):f.summary(plan,'r',now=now)

    def test_due_reserves_five_stages(self):
        plan=dict(base=dict(expires_at=time.time()+14*86400),layers=[dict(expires_at=time.time()+14*86400)]*11)
        self.assertTrue(f.summary(plan,'r')['capacity_due'])
        plan['layers']=plan['layers'][:10];self.assertFalse(f.summary(plan,'r')['capacity_due'])
        plan['base']['expires_at']=time.time()+86400;self.assertTrue(f.summary(plan,'r')['refresh_due'])
if __name__=='__main__':unittest.main()
