import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'.circleci/bridge'))
import contextlib, tempfile, unittest, shutil
from unittest import mock
import bridge
import full_driver as f
from test_bridge_rollup import clone
from test_legacy_bridge import logical

class SequentialRestoreTests(unittest.TestCase):
    def setUp(self):
        self.stack=contextlib.ExitStack();self.addCleanup(self.stack.close)
        self.root=Path(self.stack.enter_context(tempfile.TemporaryDirectory()));r=self.root
        self.state=r/'state';self.state.mkdir();self.saved=r/'saved';self.saved.mkdir()
        shards=r/'brave-workspace-checkpoint.shards';shards.mkdir()
        names=[f'{i}.zst' for i in range(8)]
        for n in names:(shards/n).write_bytes(b'base')
        raw=bridge.encode({'shards':[{'name':n} for n in names]});(r/f.d.MANIFEST).write_bytes(raw)
        head=bridge.base_id(raw);baseid=head
        self.base=r/'base';self.base.mkdir();(self.base/'a').write_text('base')
        self.work=r/'work';clone(self.base,self.work);layers=[]
        for i in range(2):
            before=bridge.begin(self.work,head,'job');(self.work/'a').write_text(str(i))
            rec=bridge.capture(self.work,before,'job',self.saved/f'{i}.zip',lambda:None)
            layers.append(dict(id=rec['id'],parent=head,key=str(i)));head=rec['id']
        self.plan=dict(base=dict(id=baseid,manifest_sha256=bridge.digest(raw)),layers=layers,head=head)
        self.receipt=dict(id='receipt',payload=dict(plan=self.plan));f.d.c.save(self.state/'selected.json',self.receipt)
        self.stack.enter_context(mock.patch.multiple(f.d,ROOT=r,STATE=self.state,LAYERS=r/'.bridge-layers',INCOMING=r/'incoming',operation_budget=1000,create=True))
        self.stack.enter_context(mock.patch.object(f.d,'valid',side_effect=lambda x:x['payload']))
        self.stack.enter_context(mock.patch.object(f.cli,'run_bounded',side_effect=lambda *args:clone(self.base,r/'brave-work')))
    def incoming(self,i):
        shutil.rmtree(f.d.INCOMING,ignore_errors=True);f.d.INCOMING.mkdir()
        shutil.copy2(self.saved/f'{i}.zip',f.d.INCOMING/'payload.zip')
        f.d.c.save(f.d.INCOMING/'envelope.json',self.plan['layers'][i])
    def test_real_ordered_replay_no_early_proof_and_capture(self):
        f.restore_base();self.assertFalse(list((self.root/'brave-workspace-checkpoint.shards').iterdir()))
        with self.assertRaises(ValueError):f.restore_finish()
        for i in range(2):
            self.incoming(i);f.restore_layer(i)
            self.assertFalse(list(f.d.LAYERS.iterdir()))
            self.assertFalse((self.state/'restored-proof.json').exists())
        for i in range(2,16):f.restore_layer(i)
        f.restore_finish();f.d.verify_restored()
        self.assertEqual(logical(self.root/'brave-work'),logical(self.work))
        self.assertEqual(bridge.root_metadata(self.root/'brave-work'),bridge.root_metadata(self.work))
        before=bridge.begin(self.root/'brave-work',self.plan['head'],'next')
        (self.root/'brave-work/new').write_text('next')
        self.assertEqual(bridge.capture(self.root/'brave-work',before,'next',self.root/'next.zip',lambda:None)['parent'],self.plan['head'])
        with self.assertRaises(ValueError):f.restore_finish()
    def test_failure_poisoned_cursor_and_remote_preserved(self):
        f.restore_base();self.incoming(0);(f.d.INCOMING/'payload.zip').write_bytes(b'corrupt')
        with self.assertRaises(ValueError):f.restore_layer(0)
        with self.assertRaises(ValueError):f.restore_layer(0)
        with self.assertRaises(ValueError):f.restore_finish()
        self.assertEqual(f.d.c.read(self.state/'selected.json'),self.receipt)
        self.assertFalse((self.state/'restored-proof.json').exists())
    def test_reordered_and_changed_receipt_fail(self):
        f.restore_base();self.incoming(1)
        with self.assertRaises(ValueError):f.restore_layer(1)
        other=dict(self.receipt,id='other');f.d.c.save(self.state/'selected.json',other)
        with self.assertRaises(ValueError):f.restore_layer(0)
    def test_base_failure_keeps_shards_no_proof(self):
        with mock.patch.object(f.cli,'run_bounded',side_effect=ValueError('extract')):
            with self.assertRaises(ValueError):f.restore_base()
        self.assertEqual(len(list((self.root/'brave-workspace-checkpoint.shards').iterdir())),8)
        with self.assertRaises(ValueError):f.restore_base()
        self.assertFalse((self.state/'restored-proof.json').exists())
    def test_symlink_incoming_and_repeat_refused(self):
        f.restore_base();self.incoming(0)
        p=f.d.INCOMING/'payload.zip';p.unlink();p.symlink_to(self.saved/'0.zip')
        with self.assertRaises(ValueError):f.restore_layer(0)
        p.unlink();shutil.copy2(self.saved/'0.zip',p);f.restore_layer(0)
        with self.assertRaises(ValueError):f.restore_layer(0)
