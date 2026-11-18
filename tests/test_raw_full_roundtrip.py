"""Real tar/zstd base + verified delta roundtrip; native cache copies are simulated."""
import contextlib,json,os,shutil,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from test_raw_full_adapter import c

@unittest.skipUnless(shutil.which('zstd'),'zstd needed for real checkpoint integration')
class FullRoundtrip(unittest.TestCase):
 def test_nested_source_seed_restore_delta_and_expiry(self):
  with tempfile.TemporaryDirectory() as directory,contextlib.ExitStack() as stack:
   root=Path(directory);state=root/'.checkpoint-state';head=root/'.checkpoint-head/receipt.json';incoming=root/'.checkpoint-incoming'
   stack.enter_context(patch.object(c,'ROOT',root))
   stack.enter_context(patch.multiple(c.D,ROOT=root,STATE=state,HEAD=head,INCOMING=incoming,LAYERS=root/'.bridge-layers',operation_budget=120,create=True))
   stack.enter_context(patch.multiple(c.D.c,ROOT=root,STATE=state,HEAD=head,INCOMING=incoming))
   stack.enter_context(patch.dict(os.environ,CIRCLE_BRANCH='raw-sandium/bootstrap',CIRCLE_PROJECT_REPONAME='Sandium-2',RAWS_CHECKPOINT_REVIEWED='true',RAWS_ALLOW_FRESH_SEED='true',RAWS_STAGE='1',RAWS_PIPELINE_NUMBER='100',CIRCLE_WORKFLOW_ID='roundtrip',CIRCLE_BUILD_NUM='1',CIRCLE_SHA1='revision'))
   c.prepare()
   work=root/'work/source';out=work/'src/out/RawSandium';out.mkdir(parents=True)
   for p in [work/'.gclient',work/'src/.git/HEAD',out/'build.ninja',out/'args.gn']:
    p.parent.mkdir(exist_ok=True,parents=True);p.write_text('fixture')
   for i in range(20):(work/'src'/f'file{i}').write_text('payload '+str(i))
   (work/'src/link').symlink_to('file1')
   c.D.c.save(root/'handoff/stage1/state.json',dict(status='slice_expired',fingerprint=c.fingerprint()))
   c.capture()
   manifest=json.loads((root/c.D.MANIFEST).read_text());self.assertEqual(len(manifest['shards']),8)
   store=root/'fake-native';store.mkdir()
   shutil.copy2(root/c.D.MANIFEST,store/c.D.MANIFEST);shutil.copytree(root/c.D.SHARDS,store/c.D.SHARDS)
   c.clear_readback();shutil.copy2(store/c.D.MANIFEST,root/c.D.MANIFEST);shutil.copytree(store/c.D.SHARDS,root/c.D.SHARDS)
   c.readback();c.publish()
   base_expiry=c.D.c.read(head)['payload']['plan']['base']['expires_at']
   self.assertLessEqual(base_expiry,time.time()+14*86400)
   # Fresh worker: no source, no stale same-job freshness/inventory proof.
   shutil.rmtree(work);shutil.rmtree(state);incoming.rmdir()
   os.environ['RAWS_STAGE']='2';os.environ['CIRCLE_BUILD_NUM']='2'
   c.prepare();c.f.restore_base()
   for slot in range(16):c.f.restore_layer(slot)
   c.f.restore_finish()
   self.assertEqual((work/'src/file1').read_text(),'payload 1')
   self.assertTrue((work/'src/link').is_symlink())
   c.begin();(work/'src/file1').write_text('changed');(work/'src/file2').unlink()
   c.D.c.save(root/'handoff/stage2/state.json',dict(status='slice_expired',fingerprint=c.fingerprint()))
   c.capture()
   self.assertEqual(c.D.c.read(state/'candidate.json')['payload']['plan']['base']['expires_at'],base_expiry)
   delta_store=store/'delta';shutil.copytree(incoming,delta_store)
   c.clear_readback();shutil.copytree(delta_store,incoming);c.readback();c.publish()
   self.assertEqual(c.D.c.read(head)['payload']['plan']['base']['expires_at'],base_expiry)
   # Third worker replays actual saved base plus delta, not merely receipt hashes.
   shutil.rmtree(work);shutil.rmtree(state);shutil.rmtree(incoming)
   shutil.rmtree(root/c.D.SHARDS);shutil.copytree(store/c.D.SHARDS,root/c.D.SHARDS)
   os.environ['RAWS_STAGE']='3';os.environ['CIRCLE_BUILD_NUM']='3'
   c.prepare();c.f.restore_base();shutil.copytree(delta_store,incoming);c.f.restore_layer(0)
   for slot in range(1,16):c.f.restore_layer(slot)
   c.f.restore_finish()
   self.assertEqual((work/'src/file1').read_text(),'changed')
   self.assertFalse((work/'src/file2').exists())
   self.assertEqual(c.D.c.read(state/'selected.json')['payload']['plan']['base']['expires_at'],base_expiry)
   # A new pipeline may select the exact complete chain without resetting expiry.
   shutil.rmtree(state)
   os.environ.update(RAWS_STAGE='1',RAWS_PIPELINE_NUMBER='101',CIRCLE_WORKFLOW_ID='next-run',CIRCLE_BUILD_NUM='4')
   c.prepare()
   self.assertEqual(len(c.D.c.read(state/'selected.json')['payload']['plan']['layers']),1)
   self.assertEqual(c.D.c.read(state/'selected.json')['payload']['plan']['base']['expires_at'],base_expiry)
