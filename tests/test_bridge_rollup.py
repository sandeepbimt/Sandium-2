import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/".circleci/bridge"))
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
import zipfile

from bridge import begin, capture, apply, base_id, digest, encode, root_metadata
from rollup import rollup
from test_legacy_bridge import logical


def clone(src, dest):
    shutil.copytree(src, dest, symlinks=True)
    seen = {}
    for p in src.rglob('*'):
        if p.is_file() and not p.is_symlink():
            st = p.stat(); key = (st.st_dev, st.st_ino); target = dest / p.relative_to(src)
            if key in seen:
                target.unlink(); os.link(seen[key], target)
            else: seen[key] = target
    for p in sorted(src.rglob('*'), key=lambda p: len(p.parts), reverse=True):
        shutil.copystat(p, dest / p.relative_to(src), follow_symlinks=False)
    shutil.copystat(src, dest)


class RollupTests(unittest.TestCase):
    def test_chain_equivalence_rename_hardlinks_delete_recreate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); base = root/'base'; base.mkdir()
            (base/'dir').mkdir(); (base/'dir/a').write_bytes(b'base'); os.link(base/'dir/a', base/'dir/b')
            (base/'stable').write_bytes(b'unchanged'*1000)
            (base/'gone').mkdir(); (base/'gone/old').write_bytes(b'old')
            (base/'replace').write_bytes(b'original'); os.symlink('dir/a', base/'sym')
            work = root/'work'; clone(base, work)
            head = base_id(b'fixture'); layers = []
            def delta(edit):
                nonlocal head
                before = begin(work, head, 'job'); edit()
                path = root/f'd{len(layers)}.zip'
                rec = capture(work, before, 'job', path, lambda:None)
                layers.append(dict(path=path,id=rec['id'])); head=rec['id']
            def first():
                (work/'dir/a').write_bytes(b'new-linked'); (work/'dir/a').rename(work/'renamed')
                shutil.rmtree(work/'gone'); (work/'replace').unlink(); (work/'temporary').write_bytes(b'obsolete'*100)
            delta(first)
            def second():
                (work/'dir/b').unlink(); (work/'renamed').write_bytes(b'final')
                (work/'gone').mkdir(); (work/'gone/new').write_bytes(b'recreated')
                (work/'replace').write_bytes(b'replaced'); (work/'temporary').unlink()
                (work/'sym').unlink(); os.symlink('renamed',work/'sym')
            delta(second)
            before = root/'before'; chain = root/'chain'; clone(base,before); clone(base,chain)
            parent=base_id(b'fixture')
            for layer in layers: parent=apply(chain,layer['path'],layer['id'],parent)
            # Rollup itself receives no base path, and works after original base removal.
            shutil.rmtree(base)
            result=rollup(base_id(b'fixture'),layers,root/'rolled.zip')
            apply(before,root/'rolled.zip',result['id'],result['parent'])
            self.assertEqual(logical(before),logical(chain)); self.assertEqual(logical(before),logical(work))
            self.assertEqual(root_metadata(before),root_metadata(work))
            with zipfile.ZipFile(root/'rolled.zip') as z:
                m=json.loads(z.read('manifest.json'))
                self.assertNotIn('stable',m['entries']);self.assertNotIn('temporary',m['entries'])
                self.assertIn('gone/old',m['deleted']);self.assertNotIn('gone',m['deleted'])

    def fixture(self, root):
        work=root/'work';work.mkdir();(work/'a').write_bytes(b'old')
        b=begin(work,'B','job');(work/'a').write_bytes(b'new')
        d=capture(work,b,'job',root/'delta',lambda:None)
        return [dict(path=root/'delta',id=d['id'])]

    def test_wrong_order_hash_and_existing_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);layers=self.fixture(root)
            with self.assertRaisesRegex(ValueError,'parent'):rollup('WRONG',layers,root/'out')
            with self.assertRaisesRegex(ValueError,'Corrupt'):rollup('B',[dict(path=layers[0]['path'],id='0'*64)],root/'out')
            (root/'out').write_bytes(b'keep')
            with self.assertRaisesRegex(ValueError,'exists'):rollup('B',layers,root/'out')
            self.assertEqual((root/'out').read_bytes(),b'keep')

    def test_bad_surviving_content_never_published(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);layers=self.fixture(root)
            with zipfile.ZipFile(layers[0]['path']) as z:items={n:z.read(n) for n in z.namelist()}
            blob=next(n for n in items if n.startswith('data/'));items[blob]=b'BAD'
            with zipfile.ZipFile(root/'bad','w') as z:
                for n,data in items.items():z.writestr(n,data)
            with self.assertRaisesRegex(ValueError,'Bad surviving'):rollup('B',[dict(path=root/'bad',id=digest((root/'bad').read_bytes()))],root/'out')
            self.assertFalse((root/'out').exists());self.assertFalse(list(root.glob('.rollup-*')))

    def test_delete_then_recreate_directory_type(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);base=root/'base';base.mkdir();(base/'node').mkdir();(base/'node/child').write_bytes(b'x')
            work=root/'work';clone(base,work);b=begin(work,'B','1')
            shutil.rmtree(work/'node');os.symlink('elsewhere',work/'node')
            d1=capture(work,b,'1',root/'d1',lambda:None);b=begin(work,d1['id'],'2')
            (work/'node').unlink();(work/'node').mkdir();(work/'node/new').write_bytes(b'y')
            d2=capture(work,b,'2',root/'d2',lambda:None)
            r=rollup('B',[dict(path=root/'d1',id=d1['id']),dict(path=root/'d2',id=d2['id'])],root/'out')
            apply(base,root/'out',r['id'],'B');self.assertEqual(logical(base),logical(work))

    def test_noop_metadata_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);base=root/'base';base.mkdir();(base/'a').write_bytes(b'a');work=root/'work';clone(base,work)
            b=begin(work,'B','1');os.chmod(work,0o750)
            d=capture(work,b,'1',root/'delta',lambda:None)
            r=rollup('B',[dict(path=root/'delta',id=d['id'])],root/'out')
            self.assertEqual(r['hashed_bytes'],0);apply(base,root/'out',r['id'],'B')
            self.assertEqual(root_metadata(base),root_metadata(work))

if __name__=='__main__': unittest.main()
