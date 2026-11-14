"""Chain restore optimization: complete state and checks, fewer full inventories."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'.circleci/bridge'))
import os
import shutil
import tempfile
import unittest
from unittest import mock
import bridge
from bridge import begin, capture, apply, apply_chain, root_metadata
from rollup import rollup
from test_legacy_bridge import logical
from test_bridge_rollup import clone


class ChainRestoreTests(unittest.TestCase):
    def fixture(self, root, count=7):
        base=root/'base';base.mkdir();(base/'dir').mkdir()
        (base/'dir/a').write_bytes(b'old');os.link(base/'dir/a',base/'dir/b')
        (base/'stable').write_bytes(b'keep');(base/'node').mkdir()
        (base/'node/old').write_bytes(b'old');os.symlink('dir/a',base/'sym')
        work=root/'work';clone(base,work);head='B';layers=[]
        for i in range(count):
            before=begin(work,head,'job')
            if i==0:
                (work/'dir/a').write_bytes(b'new');(work/'dir/a').rename(work/'renamed')
                shutil.rmtree(work/'node');os.symlink('/not-followed',work/'node')
            elif i==1:
                (work/'node').unlink();(work/'node').mkdir();(work/'node/new').write_bytes(b'new')
                (work/'sym').unlink();os.symlink('renamed',work/'sym')
            elif i==2:
                (work/'dir/b').unlink();(work/'renamed').write_bytes(b'final')
                os.chmod(work/'stable',0o600)
            else:
                (work/f'added{i}').write_bytes(str(i).encode())
            path=root/f'd{i}';r=capture(work,before,'job',path,lambda:None)
            layers.append(dict(archive=path,id=r['id'],parent=head));head=r['id']
        return base,work,layers,head

    def test_seven_layers_exact_equivalence_with_only_two_scans(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);base,work,layers,head=self.fixture(root)
            fast=root/'fast';old=root/'old';clone(base,fast);clone(base,old)
            parent='B'
            for layer in layers:parent=apply(old,layer['archive'],layer['id'],parent)
            with mock.patch.object(bridge,'inventory',wraps=bridge.inventory) as scans:
                self.assertEqual(apply_chain(fast,layers,'B'),head)
                self.assertEqual(scans.call_count,2)
            self.assertEqual(logical(fast),logical(old));self.assertEqual(logical(fast),logical(work))
            self.assertEqual(root_metadata(fast),root_metadata(work))
            # Capture still obtains fresh local device/inode/ctime baseline.
            before=begin(fast,head,'fresh-job')
            self.assertIn('ctime',before['entries']['stable'])
            self.assertEqual(before['root'],[fast.stat().st_dev,fast.stat().st_ino])
            # Imminent rollup retains all seven prior layers and the new delta.
            (fast/'next').write_bytes(b'next');r=capture(fast,before,'fresh-job',root/'d7',lambda:None)
            rolled=rollup('B',[dict(path=x['archive'],id=x['id']) for x in layers]+[dict(path=root/'d7',id=r['id'])],root/'rolled')
            restored=root/'rolled-tree';clone(base,restored)
            apply_chain(restored,[dict(archive=root/'rolled',id=rolled['id'],parent='B')],'B')
            self.assertEqual(logical(restored),logical(fast))

    def test_corrupt_later_layer_and_wrong_order_still_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);base,work,layers,head=self.fixture(root,3)
            bad=root/'bad';clone(base,bad)
            wrong=[dict(x) for x in layers];wrong[1]['id']='0'*64
            with self.assertRaisesRegex(ValueError,'Corrupt delta'):apply_chain(bad,wrong,'B')
            order=root/'order';clone(base,order)
            with self.assertRaisesRegex(ValueError,'Missing/reordered'):apply_chain(order,[layers[1],layers[0]],'B')

    def test_final_independent_inventory_detects_unexpected_mutation(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);base,work,layers,head=self.fixture(root,3);dest=root/'dest';clone(base,dest)
            original=bridge._apply
            def inject(*args,**kwargs):
                result=original(*args,**kwargs)
                if args[2]==head:(dest/'unexpected').write_bytes(b'bad')
                return result
            with mock.patch.object(bridge,'_apply',side_effect=inject):
                with self.assertRaisesRegex(ValueError,'metadata mismatch'):apply_chain(dest,layers,'B')

    def test_final_inventory_still_rejects_external_hardlink(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);base,work,layers,head=self.fixture(root,3);dest=root/'dest';clone(base,dest)
            original=bridge._apply
            def inject(*args,**kwargs):
                result=original(*args,**kwargs)
                if args[2]==head:os.link(dest/'stable',root/'outside')
                return result
            with mock.patch.object(bridge,'_apply',side_effect=inject):
                with self.assertRaisesRegex(ValueError,'External hardlinks'):apply_chain(dest,layers,'B')

    def test_single_delta_keeps_one_inventory(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);base,work,layers,head=self.fixture(root,1)
            with mock.patch.object(bridge,'inventory',wraps=bridge.inventory) as scans:
                self.assertEqual(apply_chain(base,layers,'B'),head)
                self.assertEqual(scans.call_count,1)


if __name__=='__main__':unittest.main()
