"""Full-mode sparse restore: replay exact existing delta format without tree scans."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'.circleci/bridge'))
import tempfile
import unittest
from unittest import mock
import bridge
import sparse_restore
from test_bridge_chain import ChainRestoreTests
from test_bridge_rollup import clone
from test_legacy_bridge import logical
from rollup import rollup

class SparseRestoreTests(unittest.TestCase):
    def test_chain_preserves_content_links_deletions_metadata_without_scan(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            base,work,layers,head=ChainRestoreTests().fixture(root)
            dest=root/'dest';clone(base,dest)
            with mock.patch.object(bridge,'inventory',side_effect=AssertionError('full scan')):
                self.assertEqual(sparse_restore.apply_chain(dest,layers,'B'),head)
            self.assertEqual(logical(dest),logical(work))
            self.assertEqual(bridge.root_metadata(dest),bridge.root_metadata(work))
            result=rollup('B',[dict(path=x['archive'],id=x['id']) for x in layers],root/'rollup')
            merged=root/'merged';clone(base,merged)
            sparse_restore.apply_chain(merged,[dict(archive=root/'rollup',id=result['id'],parent='B')],'B')
            self.assertEqual(logical(merged),logical(work))
    def test_unchanged_parent_timestamp_preserved(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);base=root/'base';base.mkdir();(base/'dir').mkdir()
            (base/'dir/file').write_text('before')
            work=root/'work';clone(base,work)
            before=bridge.begin(work,'B','job')
            # In-place modification changes no parent directory timestamps.
            (work/'dir/file').write_text('after')
            delta=root/'delta';result=bridge.capture(work,before,'job',delta,lambda:None)
            sparse_restore.apply_chain(base,[dict(archive=delta,id=result['id'],parent='B')],'B')
            self.assertEqual(logical(base),logical(work))

    def test_symlink_parent_and_undeclared_descendants_refused(self):
        import zipfile
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);base=root/'base';base.mkdir();(base/'keep').mkdir()
            (base/'keep/child').write_text('keep')
            import os
            os.symlink(str(root),base/'link')
            for entries,deleted in [({'link/evil':dict(kind='directory',mode=493,mtime=0)},[]), ({},['keep'])]:
                archive=root/'crafted'
                with zipfile.ZipFile(archive,'w') as z:
                    z.writestr('manifest.json',bridge.encode(dict(schema=1,parent='B',entries=entries,deleted=deleted,root_metadata=bridge.root_metadata(base))))
                ident=bridge.digest(archive.read_bytes())
                with self.assertRaises((ValueError,OSError)):
                    sparse_restore.apply_chain(base,[dict(archive=archive,id=ident,parent='B')],'B')
            self.assertEqual((base/'keep/child').read_text(),'keep')
            self.assertFalse((root/'evil').exists())

    def test_rollup_created_then_deleted_paths(self):
        import shutil
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);base=root/'base';base.mkdir();work=root/'work';clone(base,work)
            layers=[];head='B'
            for i in range(2):
                before=bridge.begin(work,head,'job')
                if i==0:
                    (work/'newdir').mkdir();(work/'newdir/temporary').write_text('temporary')
                    (work/'temporary').write_text('temporary')
                else:
                    shutil.rmtree(work/'newdir');(work/'temporary').unlink()
                archive=root/f'd{i}';r=bridge.capture(work,before,'job',archive,lambda:None)
                layers.append(dict(path=archive,id=r['id']));head=r['id']
            r=rollup('B',layers,root/'rolled')
            sparse_restore.apply_chain(base,[dict(archive=root/'rolled',id=r['id'],parent='B')],'B')
            self.assertEqual(logical(base),logical(work))

    def test_order_and_corruption_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);base,work,layers,head=ChainRestoreTests().fixture(root,2)
            with self.assertRaisesRegex(ValueError,'Missing/reordered'):
                sparse_restore.apply_chain(base,layers[::-1],'B')
            layers[0]['id']='0'*64
            with self.assertRaisesRegex(ValueError,'Corrupt delta'):
                sparse_restore.apply_chain(base,layers,'B')

if __name__=='__main__':unittest.main()
