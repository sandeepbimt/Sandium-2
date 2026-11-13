import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/".circleci/bridge"))
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from bridge import *


def logical(root):
    inv=inventory(root)
    return {n:dict(public(e),content=(Path(root)/n).read_bytes() if e['kind']=='file' else None) for n,e in inv.items()}


class BridgeTests(unittest.TestCase):
    def test_base_plus_two_deltas_and_restored_mtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);base=root/'base';base.mkdir();(base/'dir').mkdir()
            (base/'dir/stable').write_bytes(b'unchanged'*1000)
            (base/'dir/file').write_bytes(b'old');os.link(base/'dir/file',base/'dir/link')
            (base/'gone').write_bytes(b'x');os.symlink('dir/file',base/'symlink')
            # copytree does not preserve hardlinks: use a real filesystem copy helper.
            job=root/'job';shutil.copytree(base,job);(job/'dir/link').unlink();os.link(job/'dir/file',job/'dir/link');shutil.copystat(base/'dir',job/'dir')
            head=base_id(b'verified legacy manifest fixture');before=begin(job,head,'job1')
            stamp=(job/'dir/file').stat().st_mtime_ns
            (job/'dir/file').write_bytes(b'new');os.utime(job/'dir/file',ns=(stamp,stamp))
            (job/'gone').unlink();(job/'symlink').unlink();os.symlink('dir/stable',job/'symlink')
            d1=capture(job,before,'job1',root/'d1.zip',lambda:None)
            self.assertEqual(d1['hashed_bytes'],3) # unchanged base not read; linked bytes once
            fresh=root/'fresh';shutil.copytree(base,fresh);(fresh/'dir/link').unlink();os.link(fresh/'dir/file',fresh/'dir/link');shutil.copystat(base/'dir',fresh/'dir')
            apply(fresh,root/'d1.zip',d1['id'],head)
            self.assertEqual(logical(job),logical(fresh))
            before2=begin(fresh,d1['id'],'job2');(fresh/'dir/file').rename(fresh/'renamed')
            (fresh/'newdir').mkdir();(fresh/'newdir/a').write_bytes(b'added')
            d2=capture(fresh,before2,'job2',root/'d2.zip',lambda:None)
            apply(job,root/'d2.zip',d2['id'],d1['id'])
            self.assertEqual(logical(job),logical(fresh))
            with self.assertRaisesRegex(ValueError,'parent'):apply(job,root/'d2.zip',d2['id'],head)

    def test_inventory_cannot_cross_restore_or_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);work=root/'work';work.mkdir();(work/'a').write_bytes(b'x')
            before=begin(work,'base','one')
            with self.assertRaisesRegex(ValueError,'another job'):capture(work,before,'two',root/'delta',lambda:None)

    def test_mutation_during_capture_and_external_hardlink_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);work=root/'work';work.mkdir();(work/'a').write_bytes(b'x')
            before=begin(work,'base','one');calls=[]
            def gate():
                calls.append(1)
                if len(calls)==2:(work/'a').write_bytes(b'y')
            with self.assertRaisesRegex(ValueError,'Source changed'):capture(work,before,'one',root/'delta',gate)
            self.assertFalse((root/'delta').exists())
            os.link(work/'a',root/'outside')
            with self.assertRaisesRegex(ValueError,'External hardlinks'):inventory(work)

    def test_type_change_and_deleted_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);work=root/'work';work.mkdir();(work/'dir').mkdir();(work/'dir/a').write_bytes(b'a')
            before=begin(work,'base','one');other=root/'other';shutil.copytree(work,other)
            shutil.rmtree(work/'dir');os.symlink('/not-followed',work/'dir')
            d=capture(work,before,'one',root/'delta',lambda:None)
            apply(other,root/'delta',d['id'],'base');self.assertEqual(logical(work),logical(other))

    def test_old_symlink_parent_is_not_followed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);work=root/'work';work.mkdir();outside=root/'outside';outside.mkdir()
            (outside/'a').write_bytes(b'untouched');os.symlink(outside,work/'dir')
            before=begin(work,'base','one');other=root/'other';shutil.copytree(work,other,symlinks=True)
            (work/'dir').unlink();(work/'dir').mkdir();(work/'dir/a').write_bytes(b'new')
            d=capture(work,before,'one',root/'delta',lambda:None)
            apply(other,root/'delta',d['id'],'base')
            self.assertEqual((outside/'a').read_bytes(),b'untouched')
            self.assertEqual(logical(work),logical(other))

    def test_real_original_eight_shard_restore_then_delta(self):
        import subprocess
        from cli import restore_chain
        legacy=Path(__file__).resolve().parents[1]/'.circleci/scripts/sandium-checkpoint-shards.py'
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);original=root/'original';original.mkdir();work=original/'brave-work';work.mkdir()
            cached=root/'cached';cached.mkdir();shards=cached/'brave-workspace-checkpoint.shards';shards.mkdir();records=[]
            for i in range(8):
                (work/f'd{i}').mkdir();(work/f'd{i}/a').write_bytes(f'base{i}'.encode())
                name=f'{i}.tar.zst';path=shards/name
                subprocess.run(['tar','--zstd','-cf',str(path),'-C',str(original),f'brave-work/d{i}'],check=True)
                records.append(dict(name=name,size_bytes=path.stat().st_size,sha256=digest(path.read_bytes()),root_paths=[f'brave-work/d{i}']))
            manifest=encode(dict(schema_version=2,format='independent-tar+zstd-shards',shards=records))
            (cached/'brave-workspace-checkpoint.manifest.json').write_bytes(manifest)
            head=base_id(manifest);before=begin(work,head,'one');(work/'d0/a').write_bytes(b'changed')
            d=capture(work,before,'one',root/'delta',lambda:None)
            plan=dict(base_manifest_sha256=digest(manifest),head=d['id'],layers=[dict(d,archive=str(root/'delta'))])
            self.assertEqual(restore_chain(cached,plan,legacy),d['id'])
            self.assertEqual((cached/'brave-work/d0/a').read_bytes(),b'changed')
            self.assertEqual((cached/'brave-work/d7/a').read_bytes(),b'base7')
            self.assertTrue((cached/'.bridge-restored.json').exists())
            self.assertEqual(d['hashed_bytes'],7)

if __name__=='__main__':unittest.main()
