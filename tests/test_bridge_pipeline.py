import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import yaml
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.circleci/bridge'))
from bridge import digest,encode,inventory,public
DRIVER=ROOT/'.circleci/bridge/driver.py'


def logical(work):
    return {n:dict(public(e),content=(work/n).read_bytes() if e['kind']=='file' else None) for n,e in inventory(work).items()}


def fixture(root):
    original=root/'original';original.mkdir();work=original/'brave-work';work.mkdir()
    cached=root/'base';cached.mkdir();shards=cached/'brave-workspace-checkpoint.shards';shards.mkdir();records=[]
    for i in range(8):
        (work/f'd{i}').mkdir();(work/f'd{i}/a').write_bytes(f'base{i}'.encode())
        name=f'{i}.tar.zst';path=shards/name
        subprocess.run(['tar','--zstd','-cf',str(path),'-C',str(original),f'brave-work/d{i}'],check=True)
        records.append(dict(name=name,size_bytes=path.stat().st_size,sha256=digest(path.read_bytes()),root_paths=[f'brave-work/d{i}']))
    raw=encode(dict(schema_version=2,format='independent-tar+zstd-shards',shards=records))
    (cached/'brave-workspace-checkpoint.manifest.json').write_bytes(raw)
    return cached


class NativeBridge(unittest.TestCase):
    def test_config_orders_restore_inventory_upload_publication(self):
        config=yaml.safe_load((ROOT/'.circleci/config.yml').read_text())
        self.assertEqual(list(config['workflows']),['sandium-flow', 'sandium-graph-precheck'])
        for name,job in config['jobs'].items():
            text=json.dumps(job)
            self.assertNotIn('checkpoint/driver.py',text)
            if name=='sandium-graph-precheck':
                self.assertNotIn('driver.py capture',text)
                self.assertNotIn('driver.py publish',text)
                self.assertNotIn('driver.py begin',text)
                self.assertNotIn('bounded-build.sh',text)
                continue
            if name=='import-experimental-seed':
                self.assertNotIn('archive-brave-workspace.sh restore',text)
                self.assertNotIn('outgoing.key',text)
                continue
            steps=job['steps'];commands=[s.get('run',{}).get('command','') if isinstance(s,dict) else '' for s in steps]
            index=lambda token:next(i for i,c in enumerate(commands) if token in c)
            self.assertLess(index('driver.py restore'),index('driver.py begin'))
            self.assertLess(index('driver.py begin'),index('prepare-brave-source.sh'))
            artifact=next(i for i,s in enumerate(steps) if isinstance(s,dict) and 'store_artifacts' in s)
            self.assertLess(artifact,index('driver.py capture'))
            saves=[i for i,s in enumerate(steps) if isinstance(s,dict) and 'save_cache' in s]
            self.assertTrue(any(index('driver.py capture')<i<index('driver.py publish') for i in saves))

    def test_legacy_timeout_stops_descendant_processes(self):
        from cli import run_bounded
        import time
        with tempfile.TemporaryDirectory() as tmp:
            marker=Path(tmp)/'orphan'
            child="import time;from pathlib import Path;time.sleep(0.6);Path("+repr(str(marker))+").write_text('orphan')"
            parent="import subprocess,sys,time;subprocess.Popen([sys.executable,'-c',"+repr(child)+"]);time.sleep(10)"
            with self.assertRaises(subprocess.TimeoutExpired):
                run_bounded([sys.executable,'-c',parent],timeout=0.1)
            time.sleep(0.7)
            self.assertFalse(marker.exists())

    def test_real_seed_stage_next_run_rollup_and_expiry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);base=fixture(root);env=dict(os.environ,SANDIUM_EXPERIMENT_REVIEWED='true',CIRCLE_PROJECT_REPONAME='Sandium-2',
                SANDIUM_EXPERIMENT_SCOPE='sandium-exp-single-v1-bridge-fixture',SANDIUM_ALLOW_SEED_IMPORT='true',SANDIUM_PIPELINE_NUMBER='20',
                CIRCLE_WORKFLOW_ID='workflow20',CIRCLE_SHA1='a'*40)
            def run(job,phase,stage=1,build=2,slot=None,ok=True):
                args=[sys.executable,str(DRIVER),phase]+([] if slot is None else ['--slot',str(slot)])
                p=subprocess.run(args,env=dict(env,CIRCLE_WORKING_DIRECTORY=str(job),SANDIUM_STAGE=str(stage),CIRCLE_BUILD_NUM=str(build)),capture_output=True,text=True)
                if ok:self.assertEqual(p.returncode,0,p.stdout+p.stderr)
                else:self.assertNotEqual(p.returncode,0)
                return p
            def base_copy(job):
                for p in base.iterdir():
                    if p.is_dir():shutil.copytree(p,job/p.name)
                    else:shutil.copy2(p,job/p.name)
            seed=root/'seed';seed.mkdir();base_copy(seed)
            run(seed,'seed-select',0,1);run(seed,'seed-capture',0,1)
            self.assertFalse((seed/'brave-work').exists()) # no decompressed base conversion
            run(seed,'publish',0,1)
            cached=[]
            previous=seed
            for stage in (1,2):
                job=root/f'stage{stage}';job.mkdir();base_copy(job)
                shutil.copytree(previous/'.checkpoint-head',job/'.checkpoint-head')
                run(job,'select',stage,stage+1)
                for i,layer in enumerate(cached):
                    shutil.rmtree(job/'.checkpoint-incoming',ignore_errors=True);shutil.copytree(layer,job/'.checkpoint-incoming')
                    run(job,'ingest',stage,stage+1,i)
                run(job,'restore',stage,stage+1);run(job,'begin',stage,stage+1)
                if stage==1:
                    path=job/'brave-work/d0/a';stamp=path.stat().st_mtime_ns
                    path.write_bytes(b'revised');os.utime(path,ns=(stamp,stamp))
                else:(job/'brave-work/d1/a').unlink()
                run(job,'capture',stage,stage+1)
                layer=root/f'cache{stage}';shutil.copytree(job/'.checkpoint-incoming',layer);cached.append(layer)
                run(job,'publish',stage,stage+1);previous=job
            expected=logical(previous/'brave-work')
            # Near expiry is still valid, but requires delta-only rollup and compressed-base refresh.
            receipt=json.loads((previous/'.checkpoint-head/receipt.json').read_text())
            import time
            receipt['payload']['plan']['base']['expires_at']=int(time.time())+1000
            receipt['payload']['plan']['layers'][0]['expires_at']=int(time.time())+1000
            # Keep cache envelope consistent with accepted test fixture record.
            (cached[0]/'envelope.json').write_bytes(encode(receipt['payload']['plan']['layers'][0]))
            receipt['id']=digest(encode(receipt['payload']))
            (previous/'.checkpoint-head/receipt.json').write_bytes(encode(receipt))
            job=root/'next-run';job.mkdir();base_copy(job);shutil.copytree(previous/'.checkpoint-head',job/'.checkpoint-head')
            env.update(SANDIUM_PIPELINE_NUMBER='21',CIRCLE_WORKFLOW_ID='workflow21',CIRCLE_SHA1='b'*40)
            run(job,'select',1,4)
            for i,layer in enumerate(cached):
                shutil.rmtree(job/'.checkpoint-incoming',ignore_errors=True);shutil.copytree(layer,job/'.checkpoint-incoming');run(job,'ingest',1,4,i)
            run(job,'restore',1,4);self.assertEqual(logical(job/'brave-work'),expected);run(job,'begin',1,4)
            (job/'brave-work/d2/a').write_bytes(b'next')
            run(job,'capture',1,4)
            candidate=json.loads((job/'.checkpoint-state/candidate.json').read_text())['payload']['plan']
            self.assertEqual(len(candidate['layers']),1)
            self.assertEqual(candidate['layers'][0]['parent'],candidate['base']['id'])
            self.assertNotEqual(candidate['base']['key'],receipt['payload']['plan']['base']['key'])
            self.assertEqual(candidate['base']['id'],receipt['payload']['plan']['base']['id'])
            # Publish rolled delta only after simulated native upload, then reconstruct afresh.
            rolled=root/'rolled-cache';shutil.copytree(job/'.checkpoint-incoming',rolled)
            run(job,'publish',1,4)
            expected_rolled=logical(job/'brave-work')
            fresh=root/'after-rollup';fresh.mkdir();base_copy(fresh);shutil.copytree(job/'.checkpoint-head',fresh/'.checkpoint-head')
            env.update(SANDIUM_PIPELINE_NUMBER='22',CIRCLE_WORKFLOW_ID='workflow22',CIRCLE_SHA1='c'*40)
            run(fresh,'select',1,5);shutil.copytree(rolled,fresh/'.checkpoint-incoming');run(fresh,'ingest',1,5,0)
            run(fresh,'restore',1,5);self.assertEqual(logical(fresh/'brave-work'),expected_rolled)
            # Expired accepted dependency is not permission to recover base only.
            expired=json.loads((job/'.checkpoint-head/receipt.json').read_text());expired['payload']['plan']['base']['expires_at']=0
            expired['id']=digest(encode(expired['payload']));(job/'.checkpoint-head/receipt.json').write_bytes(encode(expired))
            self.assertIn('Expired dependency',run(job,'select',ok=False).stderr)

if __name__=='__main__':unittest.main()
