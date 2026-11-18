"""Ordinary Full releases only successfully consumed disposable inputs."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'.circleci/bridge'))
import tempfile
import unittest
from unittest import mock
import cli
import bridge

class ReclaimTests(unittest.TestCase):
    def fixture(self,root):
        shards=root/'raw-workspace-checkpoint.shards';shards.mkdir(parents=True)
        names=[f'shard-{i}.tar.zst' for i in range(8)]
        for name in names:(shards/name).write_bytes(b'base')
        raw=bridge.encode({'shards':[{'name':n} for n in names]})
        (root/'raw-workspace-checkpoint.manifest.json').write_bytes(raw)
        folder=root/'.bridge-layers';folder.mkdir(parents=True)
        layers=[];parent=bridge.base_id(raw)
        for i in range(2):
            p=folder/f'{i}.zip';p.write_bytes(b'delta')
            layers.append(dict(archive=str(p),id=str(i),parent=parent));parent=str(i)
        return dict(base_manifest_sha256=bridge.digest(raw),head=parent,layers=layers)
    def test_release_order_and_metadata_preserved(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);plan=self.fixture(root)
            def restore(*a):
                self.assertEqual(len(list((root/'raw-workspace-checkpoint.shards').iterdir())),8)
                (root/'work/source').mkdir(parents=True)
            def apply(work,layers,parent):
                self.assertFalse(list((root/'raw-workspace-checkpoint.shards').iterdir()))
                layer=layers[0];i=int(layer['id'])
                self.assertTrue(Path(layer['archive']).exists())
                if i:self.assertFalse((root/'.bridge-layers/0.zip').exists())
                return layer['id']
            with mock.patch.object(cli,'run_bounded',side_effect=restore),mock.patch.object(cli,'apply_chain',side_effect=apply):
                self.assertEqual(cli.restore_chain(root,plan,'unused',release_verified_inputs=True),'1')
            self.assertTrue((root/'raw-workspace-checkpoint.manifest.json').exists())
            self.assertTrue((root/'.bridge-restored.json').exists())
            self.assertFalse(list((root/'.bridge-layers').iterdir()))
    def test_failed_base_keeps_all_inputs(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);plan=self.fixture(root)
            with mock.patch.object(cli,'run_bounded',side_effect=ValueError('failed')):
                with self.assertRaises(ValueError):cli.restore_chain(root,plan,'unused',release_verified_inputs=True)
            self.assertEqual(len(list((root/'raw-workspace-checkpoint.shards').iterdir())),8)
            self.assertEqual(len(list((root/'.bridge-layers').iterdir())),2)
    def test_failed_delta_retains_failed_and_future_no_proof(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);plan=self.fixture(root)
            with mock.patch.object(cli,'run_bounded'),mock.patch.object(cli,'apply_chain',side_effect=ValueError('delta')):
                with self.assertRaises(ValueError):cli.restore_chain(root,plan,'unused',release_verified_inputs=True)
            self.assertEqual(len(list((root/'.bridge-layers').iterdir())),2)
            self.assertFalse((root/'.bridge-restored.json').exists())
    def test_default_generic_restore_keeps_inputs(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);plan=self.fixture(root)
            with mock.patch.object(cli,'run_bounded'),mock.patch.object(cli,'apply_chain',return_value='1'):
                cli.restore_chain(root,plan,'unused')
            self.assertEqual(len(list((root/'raw-workspace-checkpoint.shards').iterdir())),8)
            self.assertEqual(len(list((root/'.bridge-layers').iterdir())),2)
    def test_symlink_rejected_before_restore(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);plan=self.fixture(root)
            p=root/'.bridge-layers/0.zip';p.unlink();p.symlink_to(root/'.bridge-layers/1.zip')
            with mock.patch.object(cli,'run_bounded') as restore:
                with self.assertRaises(ValueError):cli.restore_chain(root,plan,'unused',release_verified_inputs=True)
                restore.assert_not_called()
    def test_wrong_applied_head_retains_delta(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);plan=self.fixture(root)
            with mock.patch.object(cli,'run_bounded'),mock.patch.object(cli,'apply_chain',return_value='wrong'):
                with self.assertRaises(ValueError):cli.restore_chain(root,plan,'unused',release_verified_inputs=True)
            self.assertEqual(len(list((root/'.bridge-layers').iterdir())),2)
            self.assertFalse((root/'.bridge-restored.json').exists())
    def test_outside_layer_path_rejected_before_restore(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);plan=self.fixture(root)
            plan['layers'][0]['archive']=str(root/'other.zip')
            with mock.patch.object(cli,'run_bounded') as restore:
                with self.assertRaises(ValueError):cli.restore_chain(root,plan,'unused',release_verified_inputs=True)
                restore.assert_not_called()
    def test_real_sparse_layers_then_new_capture_without_old_archives(self):
        import os
        import sparse_restore
        from test_bridge_rollup import clone
        from test_legacy_bridge import logical
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);plan=self.fixture(root)
            base=root/'base';base.mkdir(parents=True);(base/'a').write_bytes(b'base')
            os.link(base/'a',base/'linked');(base/'old').write_bytes(b'delete')
            work=root/'source';clone(base,work)
            head=bridge.base_id((root/'raw-workspace-checkpoint.manifest.json').read_bytes())
            layers=[]
            for i in range(2):
                before=bridge.begin(work,head,'capture')
                if i==0:
                    (work/'a').write_bytes(b'updated');(work/'old').unlink()
                else:
                    (work/'new').write_bytes(b'new');os.chmod(work/'a',0o600)
                path=root/'.bridge-layers'/f'{i}.zip';path.unlink()
                record=bridge.capture(work,before,'capture',path,lambda:None)
                layers.append(dict(archive=str(path),id=record['id'],parent=head));head=record['id']
            plan.update(layers=layers,head=head)
            with mock.patch.object(cli,'run_bounded',side_effect=lambda *a:clone(base,root/'work/source')),mock.patch.object(cli,'apply_chain',sparse_restore.apply_chain):
                self.assertEqual(cli.restore_chain(root,plan,'unused',release_verified_inputs=True),head)
            restored=root/'work/source'
            self.assertEqual(logical(restored),logical(work))
            self.assertEqual(bridge.root_metadata(restored),bridge.root_metadata(work))
            self.assertFalse(list((root/'.bridge-layers').iterdir()))
            self.assertFalse(list((root/'raw-workspace-checkpoint.shards').iterdir()))
            before=bridge.begin(restored,head,'next');(restored/'next').write_bytes(b'next')
            result=bridge.capture(restored,before,'next',root/'next.zip',lambda:None)
            self.assertEqual(result['parent'],head)
            self.assertTrue((root/'next.zip').is_file())
    def test_symlink_cache_directory_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);plan=self.fixture(root)
            folder=root/'.bridge-layers';folder.rename(root/'elsewhere');folder.symlink_to(root/'elsewhere',target_is_directory=True)
            with mock.patch.object(cli,'run_bounded') as restore:
                with self.assertRaises(ValueError):cli.restore_chain(root,plan,'unused',release_verified_inputs=True)
                restore.assert_not_called()
